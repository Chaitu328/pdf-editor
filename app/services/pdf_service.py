import os
import fitz
from app.utils.file_utils import generate_output_path

def has_telugu(text: str) -> bool:
    return any("\u0c00" <= ch <= "\u0c7f" for ch in text)

def get_fitted_fontsize(
    text: str,
    rect_width: float,
    rect_height: float,
    fontname: str,
    fontfile: str = None,
    default_size: float = 12,
) -> float:
    if not text.strip():
        return default_size
    try:
        if fontfile:
            font = fitz.Font(fontname=fontname, fontfile=fontfile)
            length_at_1pt = font.text_length(text, fontsize=1.0)
        else:
            length_at_1pt = fitz.get_text_length(
                text, fontname=fontname, fontsize=1.0
            )
    except Exception:
        if any("\u0c00" <= ch <= "\u0c7f" for ch in text):
            visual_chars = sum(1 for ch in text if not ("\u0c3e" <= ch <= "\u0c56" or ch == "\u0c02" or ch == "\u0c4d"))
            length_at_1pt = max(1, visual_chars) * 0.75
        else:
            length_at_1pt = len(text) * 0.55

    if length_at_1pt <= 0:
        return default_size

    fit_w = rect_width / length_at_1pt
    fit_h = rect_height / 1.15
    opt = min(default_size, fit_w, fit_h)
    return max(6.0, opt)

async def apply_edits(data: dict) -> dict:
    file_path = data.get("file_path")
    edits = data.get("edits", [])

    if not file_path:
        raise ValueError("file_path is required")

    font_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "utils",
        "Nirmala.ttf",
    )
    nirmala_available = os.path.exists(font_file)

    doc = fitz.open(file_path)
    
    # 1. Collect all redactions by page to apply them efficiently in one pass per page
    redactions_by_page = {}
    for edit in edits:
        page_num = edit.get("page", 1) - 1
        bbox = edit.get("bbox")
        if page_num < 0 or page_num >= len(doc) or not bbox:
            continue
        
        if page_num not in redactions_by_page:
            redactions_by_page[page_num] = []
        redactions_by_page[page_num].append(fitz.Rect(bbox))

    # 2. Apply all redactions (physical transparent text deletion)
    for page_num, rects in redactions_by_page.items():
        page = doc[page_num]
        for rect in rects:
            page.add_redact_annot(rect)
        # Apply redactions to remove text but keep images & vector graphics intact (transparent redaction)
        page.apply_redactions(images=0, graphics=0)

    # 3. Write new text using insert_htmlbox (with HarfBuzz shaping for Indic scripts)
    applied_count = 0
    font_dir = os.path.dirname(font_file)
    arch = fitz.Archive(font_dir) if nirmala_available else None

    for edit in edits:
        edit_type = edit.get("type")
        if edit_type == "replace_text":
            page_num = edit.get("page", 1) - 1
            bbox = edit.get("bbox")
            new_text = edit.get("new_text", "")
            fontsize = edit.get("fontsize", 12)

            if page_num < 0 or page_num >= len(doc) or not bbox:
                continue

            if not new_text.strip():
                applied_count += 1
                continue

            page = doc[page_num]
            rect = fitz.Rect(bbox)

            is_telugu = has_telugu(new_text)

            # Switch font if Telugu language matches
            if is_telugu and nirmala_available:
                fontname = "NirmalaUI"
                fontfile_path = font_file
            else:
                fontname = "helv"
                fontfile_path = None

            opt_size = get_fitted_fontsize(
                new_text, rect.width, rect.height, fontname, fontfile_path, fontsize
            )

            # Use insert_htmlbox for clean shaped rendering if archive is available
            if nirmala_available and arch:
                # Scale down slightly to prevent vertical clipping in the HTML engine
                html_font_size = min(opt_size, rect.height * 0.7)
                css = f"""
                @font-face {{
                    font-family: 'Nirmala';
                    src: url('Nirmala.ttf');
                }}
                p {{
                    font-family: 'Nirmala', sans-serif;
                    font-size: {html_font_size}pt;
                    color: black;
                    margin: 0;
                    padding: 0;
                    line-height: 1.0;
                }}
                """
                html = f"<p>{new_text}</p>"
                try:
                    page.insert_htmlbox(
                        rect,
                        html,
                        css=css,
                        archive=arch
                    )
                except Exception:
                    # Fallback if HTML box fails
                    y_baseline = rect.y0 + opt_size * 0.85
                    y_baseline = min(y_baseline, rect.y1 - 1.0)
                    page.insert_text(
                        (rect.x0, y_baseline),
                        new_text,
                        fontname=fontname,
                        fontfile=fontfile_path,
                        fontsize=opt_size,
                        color=(0, 0, 0),
                    )
            else:
                # Standard english/latin insertion if no Nirmala font available
                try:
                    page.insert_textbox(
                        rect,
                        new_text,
                        fontname=fontname,
                        fontfile=fontfile_path,
                        fontsize=opt_size,
                        color=(0, 0, 0),
                        align=fitz.TEXT_ALIGN_LEFT,
                    )
                except Exception:
                    y_baseline = rect.y0 + opt_size * 0.85
                    y_baseline = min(y_baseline, rect.y1 - 1.0)
                    page.insert_text(
                        (rect.x0, y_baseline),
                        new_text,
                        fontname=fontname,
                        fontfile=fontfile_path,
                        fontsize=opt_size,
                        color=(0, 0, 0),
                    )
            applied_count += 1
        elif edit_type == "delete_text":
            # Already handled by physical redactions in step 2
            applied_count += 1
        elif edit_type == "replace_image":
            page_num = edit.get("page", 1) - 1
            bbox = edit.get("bbox")
            image_data = edit.get("image_data")
            if page_num < 0 or page_num >= len(doc) or not bbox or not image_data:
                continue

            page = doc[page_num]
            rect = fitz.Rect(bbox)
            
            import base64
            try:
                if isinstance(image_data, str) and "," in image_data:
                    image_data = image_data.split(",", 1)[1]
                img_bytes = base64.b64decode(image_data)
                page.insert_image(rect, stream=img_bytes)
                applied_count += 1
            except Exception as e:
                print(f"Failed to insert image: {e}")

    output_path = generate_output_path()
    try:
        doc.subset_fonts()
    except Exception:
        pass
    doc.save(output_path)
    doc.close()

    return {
        "output_path": output_path,
        "edits_applied": applied_count,
    }
