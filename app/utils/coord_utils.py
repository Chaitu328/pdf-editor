def image_to_pdf_coords(
    bbox: list,
    img_width: float,
    img_height: float,
    pdf_width: float,
    pdf_height: float
) -> list[float]:
    x_scale = pdf_width / img_width
    y_scale = pdf_height / img_height

    # Convert PaddleOCR corners to PyMuPDF [x1, y1, x2, y2]
    x1 = bbox[0][0]
    y1 = bbox[0][1]
    x2 = bbox[2][0]
    y2 = bbox[2][1]

    return [
        x1 * x_scale,
        y1 * y_scale,
        x2 * x_scale,
        y2 * y_scale
    ]
