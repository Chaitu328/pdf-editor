import os
import uuid
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=dotenv_path)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "storage/uploads")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "storage/outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def save_upload(file_bytes: bytes, extension: str = "pdf") -> str:
    file_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, f"{file_id}.{extension}")
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path

def generate_output_path() -> str:
    return os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}.pdf")

def cleanup_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
