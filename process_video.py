import os
import cv2
import shutil
import boto3
import requests
import subprocess
import numpy as np
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ultralytics import YOLO

print("\n==============================")
print("   PROCESS VIDEO PIPELINE v2")
print("==============================\n")

# ============================
# CONFIG
# ============================

MODEL_URL = "https://github.com/mnavhandballcoach/handball-video-pipeline/releases/download/model/best.pt"

BUCKET_NAME = "handball-videos"
S3_ENDPOINT = "https://s3.eu-central-003.backblazeb2.com"

AWS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET = os.getenv("AWS_SECRET_ACCESS_KEY")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET
)

print("✔ S3 client initialized")
print("✔ Using YOLO model from:", MODEL_URL)
print("✔ Bucket:", BUCKET_NAME)
print("✔ Endpoint:", S3_ENDPOINT)
print("✔ SMTP host:", SMTP_HOST)
print("\n----------------------------------------\n")


# ============================
# EMAIL SENDER
# ============================

def send_email(user_email, user_name, video_url):
    print(f"📧 Sending email to {user_email}...")

    subject = "O seu vídeo anotado está pronto!"
    body = f"""
Olá {user_name},

O seu vídeo foi processado com sucesso.

Pode descarregar o vídeo anotado aqui:
{video_url}

Obrigado por utilizar o nosso serviço!
"""

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = user_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, user_email, msg.as_string())
        print("✔ Email enviado\n")
    except Exception as e:
        print("❌ Erro ao enviar email:", e)


# ============================
# DOWNLOAD MODEL
# ============================

def download_model():
    print("⬇️ Downloading YOLO model...")
    r = requests.get(MODEL_URL)
    r.raise_for_status()

    with open("best.pt", "wb") as f:
        f.write(r.content)

    print("✔ Model downloaded\n")
    return "best.pt"


# ============================
# LIST INCOMING VIDEOS
# ============================

def list_incoming():
    print("📂 Listing incoming videos...")
    resp = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix="incoming/")
    files = resp.get("Contents", [])

    video_exts = (".mp4", ".mov", ".avi", ".mkv")

    videos = [f for f in files if f["Key"].lower().endswith(video_exts)]

    print(f"✔ Found {len(videos)} videos in incoming/\n")
    return videos


# ============================
# DOWNLOAD VIDEO + JSON
# ============================

def download_video_and_json(remote_name):
    print(f"⬇️ Downloading video + JSON for {remote_name}")

    local_video = "input.mp4"
    local_json = "input.json"

    s3.download_file(BUCKET_NAME, remote_name, local_video)

    json_name = remote_name.replace(".mp4", ".json")
    s3.download_file(BUCKET_NAME, json_name, local_json)

    print("✔ Download complete\n")
    return local_video, local_json


# ============================
# CUT VIDEO
# ============================

def cut_video(input_path, start_time, duration):
    print(f"✂️ Cutting video: start={start_time}, duration={duration}")

    output_path = "cut_input.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-i", input_path,
        "-t", str(duration),
        "-c", "copy",
        output_path
    ]

    subprocess.run(cmd, check=True)
    print("✔ Cut complete\n")
    return output_path


# ============================
# FFmpeg SAFE CONVERSION
# ============================

def convert_video_to_safe_format(input_path):
    print("🎞 Converting video to safe format...")

    safe_path = "safe_input.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-movflags", "faststart",
        "-pix_fmt", "yuv420p",
        safe_path
    ]

    subprocess.run(cmd, check=True)
    print("✔ Safe video created:", safe_path, "\n")
    return safe_path


# ============================
# UPLOAD VIDEO
# ============================

def upload_video(local_path, remote_name):
    print(f"⬆️ Uploading: {remote_name}")
    s3.upload_file(local_path, BUCKET_NAME, remote_name)
    print("✔ Upload complete\n")


# ============================
# FIFA STYLE DRAWING
# ============================

COLOR_PLAYER = (180, 80, 80)
COLOR_GOALKEEPER = (120, 220, 120)
COLOR_REFEREE = (200, 200, 200)
COLOR_BALL = (255, 255, 0)

def draw_fifa_triangle(frame, x, y, color):
    pts = np.array([[x, y], [x - 14, y - 22], [x + 14, y - 22]], np.int32)
    cv2.polylines(frame, [pts], True, (0, 0, 0), 2)
    cv2.fillPoly(frame, [pts], color)

def draw_label(frame, x, y, label):
    cv2.putText(frame, label, (x - 35, y - 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3)
    cv2.putText(frame, label, (x - 35, y - 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

def draw_ball_circle(frame, x, y, w, h):
    radius = int(max(w, h) / 2)
    cx = x + w // 2
    cy = y + h // 2
    cv2.circle(frame, (cx, cy), radius, (0, 0, 0), 3)
    cv2.circle(frame, (cx, cy), radius, COLOR_BALL, 2)


# ============================
# PROCESS VIDEO (YOLO)
# ============================

def process_video(model, local_video, original_name):
    print(f"🔍 Running YOLO on {local_video}...")

    cap = cv2.VideoCapture(local_video)
    if not cap.isOpened():
        raise RuntimeError("❌ OpenCV cannot open the video.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    stable_dir = "output"
    os.makedirs(stable_dir, exist_ok=True)

    base_name = os.path.splitext(original_name)[0]
    output_video = os.path.join(stable_dir, f"{base_name}_annotated.mp4")

    writer = cv2.VideoWriter(
        output_video,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps if fps > 0 else 30,
        (w, h)
    )

    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame)
        detections = results[0].boxes

        for box in detections:
            cls = int(box.cls[0])
            label = model.names[cls].lower()

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            w_box = x2 - x1
            h_box = y2 - y1
            cx = x1 + w_box // 2

            if label == "player":
                draw_fifa_triangle(frame, cx, y1, COLOR_PLAYER)
                draw_label(frame, cx, y1, "Player")

            elif label == "goalkeeper":
                draw_fifa_triangle(frame, cx, y1, COLOR_GOALKEEPER)
                draw_label(frame, cx, y1, "Goalkeeper")

            elif label == "referee":
                draw_fifa_triangle(frame, cx, y1, COLOR_REFEREE)
                draw_label(frame, cx, y1, "Referee")

            elif label == "ball":
                draw_ball_circle(frame, x1, y1, w_box, h_box)

        writer.write(frame)
        frame_count += 1

    cap.release()
    writer.release()

    print(f"✔ Annotated video created ({frame_count} frames): {output_video}\n")
    return output_video


# ============================
# MAIN PIPELINE
# ============================

def main():
    print("🚀 Starting pipeline...\n")

    model_path = download_model()
    model = YOLO(model_path)

    files = list_incoming()
    if not files:
        print("📭 No videos to process.\n")
        return

    for file in files:
        file_name = file["Key"]
        print("\n========================================")
        print(f"🎬 PROCESSING VIDEO: {file_name}")
        print("========================================\n")

        original_name = os.path.basename(file_name)

        local_video, local_json = download_video_and_json(file_name)

        with open(local_json, "r") as f:
            data = json.load(f)

        user_email = data.get("email")
        user_name = data.get("name")
        start_time = int(data.get("start", 0))
        duration = int(data.get("duration", 0))

        if duration > 0:
            cut_path = cut_video(local_video, start_time, duration)
        else:
            cut_path = local_video

        safe_video = convert_video_to_safe_format(cut_path)

        output_video = process_video(model, safe_video, original_name)

        annotated_remote = f"processed/{os.path.basename(output_video)}"
        upload_video(output_video, annotated_remote)

        original_remote = f"processed/originals/{original_name}"
        upload_video(local_video, original_remote)

        video_url = f"https://f003.backblazeb2.com/file/{BUCKET_NAME}/{annotated_remote}"

        send_email(user_email, user_name, video_url)

        print("📦 Moving original file out of incoming/...")

        try:
            copy_source = {"Bucket": BUCKET_NAME, "Key": file_name}
            processed_original_key = file_name.replace("incoming/", "processed/originals/")

            s3.copy_object(
                Bucket=BUCKET_NAME,
                CopySource=copy_source,
                Key=processed_original_key
            )

            s3.delete_object(Bucket=BUCKET_NAME, Key=file_name)

            print(f"✔ Original moved to: {processed_original_key}\n")

        except Exception as e:
            print("❌ Error moving original file:", e)

        shutil.rmtree("output", ignore_errors=True)
        os.remove(local_video)
        os.remove(safe_video)
        os.remove(local_json)

        print("✔ Cleanup complete\n")

    print("🎉 All videos processed.\n")


if __name__ == "__main__":
    main()
