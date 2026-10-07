from fastapi import FastAPI, UploadFile, File, Form
from datetime import datetime
import json

from .b2_client import upload_bytes
from .utils import generate_video_id

app = FastAPI()


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
        "message": "Video recebido. Será processado na próxima hora.",
        "video_id": video_id
    }
