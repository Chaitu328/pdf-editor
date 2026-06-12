import os
import uuid
from dotenv import load_dotenv

# Path to app/ directory
app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(app_dir, ".env")
load_dotenv(dotenv_path=dotenv_path)

def get_abs_path(env_var: str, default_val: str) -> str:
    path = os.getenv(env_var, default_val)
    if not os.path.isabs(path):
        path = os.path.realpath(os.path.join(app_dir, path))
    return path

UPLOAD_DIR = get_abs_path("UPLOAD_DIR", "storage/uploads")
OUTPUT_DIR = get_abs_path("OUTPUT_DIR", "storage/outputs")

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
