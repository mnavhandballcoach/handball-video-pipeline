from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import os
import json
import subprocess
import boto3

# ============================================================
#   FASTAPI APP
# ============================================================

app = FastAPI()

# ============================================================
#   CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
#   STATIC HTML
# ============================================================

static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def upload_page():
    return open(os.path.join(static_dir, "upload.html"), "r", encoding="utf-8").read()

# ============================================================
#   BACKBLAZE B2 (via boto3 S3 API)
# ============================================================

BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
AWS_KEY = os.getenv("B2_KEY_ID")
AWS_SECRET = os.getenv("B2_APP_KEY")

# 🔥 ENDPOINT CORRETO DO BACKBLAZE S3
S3_ENDPOINT = "https://s3.eu-central-003.backblazeb2.com"

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET
)

UPLOAD_DIR = "/tmp/chunks"
FINAL_DIR = "/tmp/final"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)

# ============================================================
#   UPLOAD CHUNK — POST
# ============================================================

@app.post("/upload_chunk")
async def upload_chunk(
    chunk: UploadFile = None,
    index: int = Form(None),
    filename: str = Form(None),
    user_name: str = Form(None),
    user_email: str = Form(None),
    start_time: str = Form(None),
    duration: str = Form(None),
    finish: int = Form(None)
):
    # ============================================================
    #   FINALIZAÇÃO — juntar chunks e fazer upload
    # ============================================================

    if finish and filename:
        final_path = f"{FINAL_DIR}/{filename}"

        # Juntar todos os chunks
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

        # Criar JSON se metadata existir
        if user_email or user_name:
            json_path = f"{FINAL_DIR}/{filename.replace('.mp4', '.json')}"
            metadata = {
                "email": user_email,
                "name": user_name,
                "start": int(start_time) if start_time else 0,
                "duration": int(duration) if duration else 0
            }

            with open(json_path, "w") as f:
                json.dump(metadata, f)

            s3.upload_file(
                json_path,
                BUCKET_NAME,
                f"incoming/{filename.replace('.mp4', '.json')}"
            )

        # Upload do vídeo (sempre)
        s3.upload_file(final_path, BUCKET_NAME, f"incoming/{filename}")

        # Chamar pipeline
        try:
            subprocess.Popen(["python", "/app/process_video.py"])
        except Exception as e:
            print("Erro ao chamar pipeline:", e)

        return {"status": "completed", "video": filename}

    # ============================================================
    #   RECEBER CHUNK NORMAL
    # ============================================================

    if not filename or index is None or chunk is None:
        return {"status": "error", "detail": "chunk, index e filename são obrigatórios"}

    part_path = f"{UPLOAD_DIR}/{filename}.part{index}"

    with open(part_path, "wb") as f:
        f.write(await chunk.read())

    return {"status": "ok", "chunk": index}
