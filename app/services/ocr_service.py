import os
# CRITICAL: Prevent CPU environment clashes BEFORE loading Paddle modules
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import io
import fitz
from PIL import Image
from fastapi import UploadFile
import numpy as np
import pandas as pd

from app.utils.file_utils import save_upload
from app.utils.coord_utils import image_to_pdf_coords

_ocr_instances = {}
OCR_LANG = os.getenv("OCR_LANG", "te")
IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png"]

def get_ocr(lang: str = OCR_LANG):
    global _ocr_instances
    if lang in _ocr_instances:
        return _ocr_instances[lang]
    try:
        from paddleocr import PaddleOCR
        import paddleocr as _po_module
        version_str = getattr(_po_module, "__version__", "2.0.0")
        major = int(version_str.split(".")[0])

        if major >= 3:
            ocr = PaddleOCR(
                lang=lang,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
            )
        else:
            ocr = PaddleOCR(
                use_angle_cls=True,
                lang=lang,
                show_log=False,
                enable_mkldnn=False,
            )
        _ocr_instances[lang] = ocr
    except Exception as exc:
        raise RuntimeError(f"Failed to initialise PaddleOCR for lang {lang}: {exc}") from exc
    return ocr

def has_telugu(text: str) -> bool:
    return any("\u0c00" <= ch <= "\u0c7f" for ch in text)

def get_iou(box1, box2):
    x_left = max(box1[0], box2[0])
    y_top = max(box1[1], box2[1])
    x_right = min(box1[2], box2[2])
    y_bottom = min(box1[3], box2[3])

    if x_right <= x_left or y_bottom <= y_top:
        return 0.0

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = area1 + area2 - intersection_area
    return intersection_area / union_area if union_area > 0 else 0.0

def _run_ocr(ocr, img_np: np.ndarray) -> list:
    raw = None
    if hasattr(ocr, "predict"):
        try:
            raw = list(ocr.predict(img_np))
        except Exception as e:
            print(f"[OCR] predict() failed, falling back: {e}")

    if raw is None and hasattr(ocr, "ocr"):
        try:
            import paddleocr as _po_module
            major = int(getattr(_po_module, "__version__", "2.0.0").split(".")[0])
            raw = ocr.ocr(img_np) if major >= 3 else ocr.ocr(img_np, cls=True)
        except Exception as e:
            print(f"[OCR] ocr() fallback failed: {e}")

    if not raw:
        return []

    lines = []
    first = raw[0]

    # Model format parsing
    if hasattr(first, "rec_res"):
        rec_list = first.rec_res
        boxes = getattr(first, "dt_boxes", []) or []
        for bbox, (text, conf) in zip(boxes, rec_list):
            lines.append((_as_4pt(bbox), str(text), float(conf)))
        return lines

    if isinstance(first, dict):
        if "rec_texts" in first:
            recs_texts = first.get("rec_texts", [])
            recs_scores = first.get("rec_scores", [])
            boxes = first.get("rec_boxes", []) or first.get("dt_boxes", []) or []
            for bbox, text, conf in zip(boxes, recs_texts, recs_scores):
                lines.append((_as_4pt(bbox), str(text), float(conf)))
            return lines
        else:
            recs = first.get("rec_res", [])
            boxes = first.get("dt_boxes", []) or []
            for bbox, rec in zip(boxes, recs):
                text, conf = (rec[0], rec[1]) if isinstance(rec, (list, tuple)) else (str(rec), 1.0)
                lines.append((_as_4pt(bbox), str(text), float(conf)))
            return lines

    if isinstance(first, list):
        for item in first:
            if item and len(item) == 2:
                bbox_raw, rec = item
                if isinstance(rec, (list, tuple)) and len(rec) == 2:
                    text, conf = rec
                    lines.append((_as_4pt(bbox_raw), str(text), float(conf)))
    return lines

def _as_4pt(bbox) -> list:
    if isinstance(bbox, np.ndarray):
        bbox = bbox.tolist()
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        if isinstance(bbox[0], (list, tuple)):
            return [list(p) for p in bbox]
        x1, y1, x2, y2 = bbox
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    return bbox

def group_and_merge_ocr_words(words_list: list, pdf_width: float, pdf_height: float) -> list:
    if not words_list:
        return []

    df = pd.DataFrame(words_list)
    median_height = df["height"].median()
    if pd.isna(median_height) or median_height <= 0:
        median_height = 12.0

    y_coords = df["y_mid"].tolist()
    sigma = max(2.0, median_height * 0.3)

    y_min = max(0.0, min(y_coords) - 20)
    y_max = min(pdf_height, max(y_coords) + 20)
    grid = np.arange(y_min, y_max, 1.0)

    if len(grid) == 0:
        peaks = sorted(set(y_coords))
    else:
        y_arr = np.array(y_coords)
        densities = np.array([np.sum(np.exp(-((g - y_arr) ** 2) / (2 * sigma ** 2))) for g in grid])
        peaks = [grid[i] for i in range(1, len(densities) - 1) if densities[i] > densities[i - 1] and densities[i] > densities[i + 1] and densities[i] > 0.1]
        if not peaks:
            peaks = sorted(set(y_coords))

    peaks_arr = np.array(peaks)
    df["line_id"] = [int(np.argmin(np.abs(peaks_arr - row["y_mid"]))) for _, row in df.iterrows()]

    merged_blocks = []
    for _, line_df in df.groupby("line_id"):
        line_df = line_df.sort_values("x1").reset_index(drop=True)
        char_widths = line_df["width"] / line_df["text"].str.len().clip(lower=1)
        med_cw = char_widths.median()
        if pd.isna(med_cw) or med_cw <= 0:
            med_cw = 8.0
        h_threshold = max(12.0, med_cw * 2.5)

        current = []
        for _, row in line_df.iterrows():
            if not current:
                current.append(row)
            elif row["x1"] - current[-1]["x2"] <= h_threshold:
                current.append(row)
            else:
                merged_blocks.append(_merge_block(current))
                current = [row]
        if current:
            merged_blocks.append(_merge_block(current))

    return sorted(merged_blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))

def _merge_block(block: list) -> dict:
    return {
        "text": " ".join(r["text"] for r in block),
        "confidence": float(np.mean([r["confidence"] for r in block])),
        "bbox": [
            min(r["x1"] for r in block),
            min(r["y1"] for r in block),
            max(r["x2"] for r in block),
            max(r["y2"] for r in block),
        ],
    }

async def analyze_pdf(file: UploadFile, content_type: str) -> dict:
    file_bytes = await file.read()
    if content_type in IMAGE_TYPES:
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PDF")
        file_path = save_upload(buf.getvalue(), extension="pdf")
    else:
        file_path = save_upload(file_bytes, extension="pdf")

    # Initialize both OCR engines: primary (e.g. Telugu) and English fallback
    ocr_primary = get_ocr(OCR_LANG)
    ocr_en = get_ocr("en")

    doc = fitz.open(file_path)
    pages = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        pdf_width = page.rect.width
        pdf_height = page.rect.height

        pix = page.get_pixmap(dpi=300)
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n).copy()
        if pix.n == 4:
            img_np = img_np[:, :, :3]
        img_width, img_height = pix.width, pix.height

        # Run Primary Language OCR
        parsed_primary = _run_ocr(ocr_primary, img_np)
        words_primary = []
        for bbox_4pt, text, confidence in parsed_primary:
            pdf_bbox = image_to_pdf_coords(bbox_4pt, img_width, img_height, pdf_width, pdf_height)
            x1, y1, x2, y2 = pdf_bbox
            if x2 <= x1 or y2 <= y1:
                continue
            words_primary.append({
                "text": text,
                "confidence": confidence,
                "x1": x1, "y1": y1,
                "x2": x2, "y2": y2,
                "height": y2 - y1,
                "width": x2 - x1,
                "y_mid": (y1 + y2) / 2.0,
            })
        merged_primary = group_and_merge_ocr_words(words_primary, pdf_width, pdf_height)

        # Run English OCR if primary is not English
        if OCR_LANG != "en":
            parsed_en = _run_ocr(ocr_en, img_np)
            words_en = []
            for bbox_4pt, text, confidence in parsed_en:
                pdf_bbox = image_to_pdf_coords(bbox_4pt, img_width, img_height, pdf_width, pdf_height)
                x1, y1, x2, y2 = pdf_bbox
                if x2 <= x1 or y2 <= y1:
                    continue
                words_en.append({
                    "text": text,
                    "confidence": confidence,
                    "x1": x1, "y1": y1,
                    "x2": x2, "y2": y2,
                    "height": y2 - y1,
                    "width": x2 - x1,
                    "y_mid": (y1 + y2) / 2.0,
                })
            merged_en = group_and_merge_ocr_words(words_en, pdf_width, pdf_height)

            # Perform line-level bilingual merge
            final_merged = []
            used_english_indices = set()

            for t_line in merged_primary:
                t_text = t_line["text"]
                t_box = t_line["bbox"]

                if has_telugu(t_text):
                    # Telugu script region: retain primary language OCR results
                    final_merged.append(t_line)
                else:
                    # English text region: find the best overlapping English OCR line
                    best_iou = 0.0
                    best_e_idx = -1
                    for e_idx, e_line in enumerate(merged_en):
                        iou = get_iou(t_box, e_line["bbox"])
                        if iou > best_iou:
                            best_iou = iou
                            best_e_idx = e_idx

                    if best_e_idx != -1 and best_iou > 0.25:
                        e_line = merged_en[best_e_idx]
                        final_merged.append({
                            "text": e_line["text"],
                            "confidence": e_line["confidence"],
                            "bbox": e_line["bbox"] # Use English coords for precise alignment
                        })
                        used_english_indices.add(best_e_idx)
                    else:
                        # Fallback if no overlapping English line detected
                        final_merged.append(t_line)

            # Proactively append any English text lines that were completely missed by the primary OCR
            for e_idx, e_line in enumerate(merged_en):
                if e_idx in used_english_indices:
                    continue
                
                overlaps_telugu = False
                for f_line in final_merged:
                    if has_telugu(f_line["text"]):
                        if get_iou(e_line["bbox"], f_line["bbox"]) > 0.3:
                            overlaps_telugu = True
                            break
                
                if not overlaps_telugu:
                    final_merged.append(e_line)

            # Sort merged lines top-to-bottom
            final_merged.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
        else:
            final_merged = merged_primary

        texts = [
            {
                "id": f"p{page_index + 1}_t{idx}",
                "text": blk["text"],
                "confidence": round(blk["confidence"], 4),
                "bbox": [round(v, 2) for v in blk["bbox"]],
            }
            for idx, blk in enumerate(final_merged)
        ]

        pages.append({
            "page": page_index + 1,
            "width": round(pdf_width, 2),
            "height": round(pdf_height, 2),
            "texts": texts,
        })

    doc.close()
    return {"file_path": file_path, "total_pages": len(pages), "pages": pages}
