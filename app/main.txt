from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
import os
import b2sdk.v2 as b2

app = FastAPI()

# === Backblaze B2 Setup ===
info = b2.InMemoryAccountInfo()
b2_api = b2.B2Api(info)
b2_api.authorize_account(
    "production",
    os.getenv("B2_KEY_ID"),
    os.getenv("B2_APP_KEY")
)

bucket = b2_api.get_bucket_by_name(os.getenv("B2_BUCKET_NAME"))

@app.post("/upload")
async def upload_video(file: UploadFile, user_email: str = Form(...)):
    content = await file.read()

    video_id = file.filename.replace(".mp4", "")
    video_path = f"incoming/{video_id}.mp4"
    json_path = f"incoming/{video_id}.json"

    # Upload do vídeo
    bucket.upload_bytes(
        content,
        video_path,
        content_type="video/mp4"
    )

    # Upload do JSON
    meta = {
        "video_id": video_id,
        "user_email": user_email
    }

    bucket.upload_bytes(
        str(meta).encode(),
        json_path,
        content_type="application/json"
    )

    return JSONResponse({"status": "ok", "video_id": video_id})
