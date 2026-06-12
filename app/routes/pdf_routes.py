import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Header
from fastapi.responses import FileResponse

from app.services.ocr_service import analyze_pdf
from app.services.pdf_service import apply_edits

router = APIRouter(prefix="/pdf", tags=["PDF"])
API_KEY = os.getenv("API_KEY", "")

def verify_api_key(x_api_key: str = Header(...)):
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

ALLOWED_TYPES = {
    "application/pdf":  "pdf",
    "image/jpeg":       "jpg",
    "image/jpg":        "jpg",
    "image/png":        "png",
}

@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    _: None = Depends(verify_api_key)
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF, JPG, PNG files are accepted")
    result = await analyze_pdf(file, file.content_type)
    return {"success": True, "data": result}

@router.post("/apply-edits")
async def edit(
    data: dict,
    _: None = Depends(verify_api_key)
):
    try:
        result = await apply_edits(data)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/download")
async def download(
    path: str,
    _: None = Depends(verify_api_key)
):
    requested = os.path.realpath(os.path.abspath(path))
    if not os.path.exists(requested):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    storage_dir_raw = os.getenv("STORAGE_DIR", "storage")
    storage_dir = os.path.realpath(os.path.abspath(storage_dir_raw))

    if not requested.startswith(storage_dir + os.sep) and requested != storage_dir:
        raise HTTPException(status_code=403, detail="Access denied.")

    return FileResponse(
        path=requested,
        media_type="application/pdf",
        filename=os.path.basename(requested)
    )
