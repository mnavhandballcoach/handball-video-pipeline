from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import os
import json
import subprocess
import boto3

# ============================================================
#   IMPORTAR ROUTER DO UPLOAD
# ============================================================

from api.upload_chunk import router as upload_router

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

S3_ENDPOINT = "https://s3.eu-central-003.backblazeb2.com"

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET
)

# ============================================================
#   DIRECTÓRIOS TEMPORÁRIOS
# ============================================================

UPLOAD_DIR = "/tmp/chunks"
FINAL_DIR = "/tmp/final"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)

# ============================================================
#   INCLUIR ROUTER DO UPLOAD
# ============================================================

app.include_router(upload_router)

# ============================================================
#   PIPELINE (opcional, se quiseres manter aqui)
# ============================================================

@app.post("/run_pipeline")
def run_pipeline():
    try:
        subprocess.Popen(["python", "/app/process_video.py"])
        return {"status": "pipeline_started"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
