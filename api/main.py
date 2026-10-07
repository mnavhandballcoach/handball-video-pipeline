from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from pathlib import Path
import json

from .b2_client import upload_bytes
from .utils import generate_video_id

app = FastAPI()

# === Servir HTML e ficheiros estáticos ===
static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def upload_page():
    return (static_dir / "upload.html").read_text(encoding="utf-8")


# === Endpoint principal de upload ===
@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    user_email: str = Form(...)
):
    video_id = generate_video_id()

    video_path = f"incoming/{video_id}.mp4"
    meta_path = f"incoming/{video_id}.json"

    # guardar vídeo
    content = await file.read()
    upload_bytes(video_path, content, content_type="video/mp4")

    # guardar metadados
    meta = {
        "video_id": video_id,
        "original_filename": file.filename,
        "user_email": user_email,
        "created_at": datetime.utcnow().isoformat(),
        "status": "pending"
    }
    upload_bytes(meta_path, json.dumps(meta).encode(), content_type="application/json")

    return {
        "message": "Vídeo recebido. Será processado na próxima hora.",
        "video_id": video_id
    }
