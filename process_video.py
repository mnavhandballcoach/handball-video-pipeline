import os
import requests
import shutil
import boto3
from ultralytics import YOLO

print("USING LATEST VERSION 2")
YOLO

# === MODEL FROM GITHUB RELEASE ===
MODEL_URL = "https://github.com/mnavhandballcoach/handball-video-pipeline/releases/download/model/best.pt"

# === BACKBLAZE S3 CONFIG ===
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

print("USING LATEST VERSION")


# === DOWNLOAD MODEL ===
def download_model():
    print("Downloading YOLO model from GitHub Release...")

    r = requests.get(MODEL_URL)
    r.raise_for_status()

    with open("best.pt", "wb") as f:
        f.write(r.content)

    print("Model downloaded successfully.")
    return "best.pt"


# === LIST INCOMING VIDEOS (FILTER ONLY VIDEO FILES) ===
def list_incoming():
    resp = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix="incoming/")
    files = resp.get("Contents", [])

    video_exts = (".mp4", ".mov", ".mkv", ".avi")

    video_files = [
        f for f in files
        if f["Key"].lower().endswith(video_exts)
    ]

    return video_files


# === DOWNLOAD VIDEO ===
def download_video(remote_name, local_path):
    s3.download_file(BUCKET_NAME, remote_name, local_path)
    return local_path


# === UPLOAD VIDEO ===
def upload_video(local_path, remote_name):
    s3.upload_file(local_path, BUCKET_NAME, remote_name)


# === PROCESS VIDEO ===
def process_video(model, local_video):
    print(f"Running YOLO on {local_video}...")

    # Force YOLO to save inside the repo workspace
    results = model.predict(
        local_video,
        save=True,
        project="runs",       # force output folder
        name="detect"         # force subfolder
    )

    # YOLO always saves the annotated video with the same name
    output_dir = results[0].save_dir
    output_video = os.path.join(output_dir, os.path.basename(local_video))

    print(f"YOLO output saved to: {output_video}")
    return output_video


# === MAIN PIPELINE ===
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

        local_input = "input.mp4"
        download_video(file_name, local_input)

        output_video = process_video(model, local_input)

        annotated_remote = f"processed/{os.path.basename(file_name)}"
        upload_video(output_video, annotated_remote)

        original_remote = f"processed/originals/{os.path.basename(file_name)}"
        upload_video(local_input, original_remote)

        print(f"Processed and uploaded: {annotated_remote}")

        shutil.rmtree(os.path.dirname(output_video), ignore_errors=True)
        os.remove(local_input)

    print("\nAll videos processed.")


if __name__ == "__main__":
    main()
