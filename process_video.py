import os
import requests
import shutil
import boto3
import cv2
from ultralytics import YOLO

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

print("USING LATEST VERSION 2")


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


# === PROCESS VIDEO (YOLO + BUILD VIDEO MANUALLY) ===
def process_video(model, local_video, original_name):
    print(f"Running YOLO on {local_video}...")

    # Run YOLO and save frames
    results = model.predict(local_video, save=True)

    output_dir = results[0].save_dir
    print(f"YOLO saved frames to: {output_dir}")

    # Collect frames
    frames = sorted([
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.lower().endswith((".jpg", ".png"))
    ])

    if not frames:
        raise FileNotFoundError("YOLO did not generate any frames.")

    # Read first frame to get size
    first = cv2.imread(frames[0])
    h, w, _ = first.shape

    # Create stable output folder
    stable_dir = "output"
    os.makedirs(stable_dir, exist_ok=True)

    # Build final annotated video name
    base_name = os.path.splitext(original_name)[0]
    output_video = os.path.join(stable_dir, f"{base_name}_annotated.mp4")

    # Build video from frames
    writer = cv2.VideoWriter(
        output_video,
        cv2.VideoWriter_fourcc(*"mp4v"),
        30,
        (w, h)
    )

    for frame_path in frames:
        frame = cv2.imread(frame_path)
        writer.write(frame)

    writer.release()

    print(f"Final annotated video created: {output_video}")
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

        original_name = os.path.basename(file_name)

        local_input = "input.mp4"
        download_video(file_name, local_input)

        output_video = process_video(model, local_input, original_name)

        annotated_remote = f"processed/{os.path.basename(output_video)}"
        upload_video(output_video, annotated_remote)

        original_remote = f"processed/originals/{original_name}"
        upload_video(local_input, original_remote)

        print(f"Processed and uploaded: {annotated_remote}")

        shutil.rmtree("output", ignore_errors=True)
        shutil.rmtree(os.path.dirname(results[0].save_dir), ignore_errors=True)
        os.remove(local_input)

    print("\nAll videos processed.")


if __name__ == "__main__":
    main()
