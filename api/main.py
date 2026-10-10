from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import subprocess
import boto3
from api.upload_chunk import router as chunk_router

app.include_router(chunk_router)

app = FastAPI()

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Servir HTML ===
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def upload_page():
    return open(os.path.join(static_dir, "upload.html"), "r", encoding="utf-8").read()

# === Backblaze B2 (via boto3 S3 API) ===
BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
S3_ENDPOINT = os.getenv("B2_ENDPOINT")

AWS_KEY = os.getenv("B2_KEY_ID")
AWS_SECRET = os.getenv("B2_APP_KEY")

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
    finish: int = None
):

    # ============================================================
    #   FINALIZAÇÃO — juntar chunks e fazer upload
    # ============================================================

    if finish == 1:
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

        # ============================================================
        #   Criar JSON apenas se metadata existir
        # ============================================================

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

            s3.upload_file(json_path, BUCKET_NAME, f"incoming/{filename.replace('.mp4', '.json')}")

        # ============================================================
        #   Upload do vídeo (SEMPRE)
        # ============================================================

        s3.upload_file(final_path, BUCKET_NAME, f"incoming/{filename}")

        # ============================================================
        #   Chamar pipeline
        # ============================================================

        subprocess.Popen(["python3", "process_video.py"])

        return {"status": "completed", "video": filename}

    # ============================================================
    #   RECEBER CHUNK NORMAL
    # ============================================================

    part_path = f"{UPLOAD_DIR}/{filename}.part{index}"

    with open(part_path, "wb") as f:
        f.write(await chunk.read())

    return {"status": "ok", "chunk": index}


# ============================================================
#   GET /upload_chunk — evitar 405 no Safari e bots
# ============================================================

@app.get("/upload_chunk")
def upload_chunk_get():
    return {"status": "use POST for chunks", "finish": "use GET only with filename"}
