import os
import cv2
import shutil
import boto3
import requests
import subprocess
from ultralytics import YOLO

print("----")
print("----")
print("Process Video - 09102026 - 14:34")
print("----")
print("----")

# ============================
# CONFIG
# ============================

MODEL_URL = "https://github.com/mnavhandballcoach/handball-video-pipeline/releases/download/model/best.pt"

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

print("USING LATEST VERSION 4")


# ============================
# DOWNLOAD MODEL
# ============================

def download_model():
    print("Downloading YOLO model from GitHub Release...")
    r = requests.get(MODEL_URL)
    r.raise_for_status()

    with open("best.pt", "wb") as f:
        f.write(r.content)

    print("Model downloaded successfully.")
    return "best.pt"


# ============================
# LIST INCOMING VIDEOS
# ============================

def list_incoming():
    resp = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix="incoming/")
    files = resp.get("Contents", [])

    video_exts = (".mp4", ".mov", ".avi", ".mkv")

    return [
        f for f in files
        if f["Key"].lower().endswith(video_exts)
    ]


# ============================
# DOWNLOAD VIDEO
# ============================

def download_video(remote_name, local_path):
    s3.download_file(BUCKET_NAME, remote_name, local_path)
    return local_path


# ============================
# FFmpeg SAFE CONVERSION
# ============================

def convert_video_to_safe_format(input_path):
    safe_path = "safe_input.mp4"

    print("Converting video to safe format with FFmpeg...")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-movflags", "faststart",
        "-pix_fmt", "yuv420p",
        safe_path
    ]

    subprocess.run(cmd, check=True)
    print("Safe video created:", safe_path)
    return safe_path


# ============================
# UPLOAD VIDEO
# ============================

def upload_video(local_path, remote_name):
    s3.upload_file(local_path, BUCKET_NAME, remote_name)


# ============================
# PROCESS VIDEO (FRAME-BY-FRAME YOLO)
# ============================

def process_video(model, local_video, original_name):
    print(f"Running YOLO frame-by-frame on {local_video}...")

    cap = cv2.VideoCapture(local_video)
    if not cap.isOpened():
        raise RuntimeError("OpenCV cannot open the video.")

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

        # YOLO inference on frame
        results = model(frame)

        # Draw detections
        annotated = results[0].plot()

        writer.write(annotated)
        frame_count += 1

    cap.release()
    writer.release()

    print(f"Annotated video created with {frame_count} frames: {output_video}")
    return output_video


# ============================
# MAIN PIPELINE
# ============================

def main():
    print("Downloading model...")
    model_path = download_model()
    model = YOLO(model_path)

    print("Listing incoming videos...")
    files = list_incoming()

    if not files:
        print("No videos to process.")
        return

    for file in files:
        file_name = file["Key"]
        print(f"\nProcessing: {file_name}")

        original_name = os.path.basename(file_name)

        local_input = "input.mp4"
        download_video(file_name, local_input)

        safe_video = convert_video_to_safe_format(local_input)

        output_video = process_video(model, safe_video, original_name)

        annotated_remote = f"processed/{os.path.basename(output_video)}"
        upload_video(output_video, annotated_remote)

        original_remote = f"processed/originals/{original_name}"
        upload_video(local_input, original_remote)

        print(f"Processed and uploaded: {annotated_remote}")

        shutil.rmtree("output", ignore_errors=True)
        os.remove(local_input)
        os.remove(safe_video)

    print("\nAll videos processed.")


if __name__ == "__main__":
    main()
