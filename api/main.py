from fastapi import FastAPI, UploadFile, Form, Request
import os
import subprocess
import json
import boto3

app = FastAPI()

# ============================
# CONFIG
# ============================

UPLOAD_DIR = "/tmp/chunks"
FINAL_DIR = "/tmp/final"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)

BUCKET_NAME = "handball-videos"
S3_ENDPOINT = "https://s3.eu-central-003.backblazeb2.com"

AWS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET = os.getenv("AWS_SECRET_ACCESS_KEY")

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET
)

# ============================
# UPLOAD CHUNK
# ============================

@app.post("/upload_chunk")
async def upload_chunk(
    chunk: UploadFile = None,
    index: int = Form(None),
    filename: str = Form(None),
    user_name: str = Form(None),
    user_email: str = Form(None),
    start_time: str = Form(None),
    duration: str = Form(None),
    finish: int = None
):

    # ============================
    # 1) FINALIZAÇÃO → juntar chunks
    # ============================

    if finish == 1:
        final_path = f"{FINAL_DIR}/{filename}"

        with open(final_path, "wb") as outfile:
            i = 0
            while True:
                part = f"{UPLOAD_DIR}/{filename}.part{i}"
                if not os.path.exists(part):
                    break
                with open(part, "rb") as infile:
                    outfile.write(infile.read())
                os.remove(part)
                i += 1

        # ============================
        # 2) Criar JSON com metadata
        # ============================

        json_path = f"{FINAL_DIR}/{filename.replace('.mp4', '.json')}"
        metadata = {
            "email": user_email,
            "name": user_name,
            "start": int(start_time) if start_time else 0,
            "duration": int(duration) if duration else 0
        }

        with open(json_path, "w") as f:
            json.dump(metadata, f)

        # ============================
        # 3) Upload para Backblaze
        # ============================

        remote_video = f"incoming/{filename}"
        remote_json = f"incoming/{filename.replace('.mp4', '.json')}"

        s3.upload_file(final_path, BUCKET_NAME, remote_video)
        s3.upload_file(json_path, BUCKET_NAME, remote_json)

        # ============================
        # 4) Chamar pipeline
        # ============================

        subprocess.Popen(["python3", "process_video.py"])

        return {
            "status": "completed",
            "video": remote_video,
            "json": remote_json
        }

    # ============================
    # 5) RECEBER CHUNK NORMAL
    # ============================

    part_path = f"{UPLOAD_DIR}/{filename}.part{index}"

    with open(part_path, "wb") as f:
        f.write(await chunk.read())

    return {"status": "ok", "chunk": index}
