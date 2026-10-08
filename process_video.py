import os
import requests
import base64
import shutil
from ultralytics import YOLO

# === ENV VARS FROM GITHUB SECRETS ===
KEY_ID = os.getenv("B2_KEY_ID")
APP_KEY = os.getenv("B2_APP_KEY")
BUCKET_ID = os.getenv("B2_BUCKET_ID")
BUCKET_NAME = os.getenv("B2_BUCKET_NAME")

# === AUTHENTICATION ===
def b2_auth():
    auth_str = f"{KEY_ID}:{APP_KEY}"
    encoded = base64.b64encode(auth_str.encode()).decode()

    r = requests.get(
        "https://api.backblazeb2.com/b2api/v2/b2_authorize_account",
        headers={"Authorization": f"Basic {encoded}"}
    )
    r.raise_for_status()
    return r.json()


# === LIST FILES ===
def list_files(api, prefix="incoming/"):
    url = api["apiUrl"] + "/b2api/v2/b2_list_file_names"
    r = requests.post(url, json={"bucketId": BUCKET_ID, "prefix": prefix})
    r.raise_for_status()
    return r.json().get("files", [])


# === DOWNLOAD FILE (B2 NATIVE, CORRECT) ===
def download_file(api, file_name, local_path):
    # 1) Pedir token de download para a pasta "models"
    url = api["apiUrl"] + "/b2api/v2/b2_get_download_authorization"
    payload = {
        "bucketId": BUCKET_ID,
        "fileNamePrefix": "models",   # sem barra no fim
        "validDurationInSeconds": 3600
    }
    r = requests.post(url, json=payload)
    r.raise_for_status()
    token = r.json()["authorizationToken"]

    # 2) Construir URL de download
    download_url = api["downloadUrl"] + f"/file/{BUCKET_NAME}/{file_name}"

    # 3) Fazer download com token
    headers = {"Authorization": token}
    r = requests.get(download_url, headers=headers)
    r.raise_for_status()

    with open(local_path, "wb") as f:
        f.write(r.content)

    return local_path

# === UPLOAD FILE ===
def upload_file(api, local_path, remote_name, content_type="video/mp4"):
    url = api["apiUrl"] + "/b2api/v2/b2_get_upload_url"
    r = requests.post(url, json={"bucketId": BUCKET_ID})
    r.raise_for_status()
    upload_data = r.json()

    with open(local_path, "rb") as f:
        data = f.read()

    headers = {
        "Authorization": upload_data["authorizationToken"],
        "X-Bz-File-Name": remote_name,
        "Content-Type": content_type,
        "X-Bz-Content-Sha1": "do_not_verify"
    }

    r = requests.post(upload_data["uploadUrl"], headers=headers, data=data)
    r.raise_for_status()


# === DOWNLOAD MODEL ===
def download_model(api):
    model_remote = "models/best.pt"
    model_local = "best.pt"

    print("Downloading YOLO model...")
    download_file(api, model_remote, model_local)
    return model_local


# === PROCESS VIDEO ===
def process_video(model, local_video):
    print(f"Running YOLO on {local_video}...")
    results = model.predict(local_video, save=True)

    output_dir = results[0].save_dir
    output_video = os.path.join(output_dir, os.path.basename(local_video))

    return output_video


# === MAIN PIPELINE ===
def main():
    print("Authenticating with Backblaze...")
    api = b2_auth()

    print("Downloading model...")
    model_path = download_model(api)
    model = YOLO(model_path)

    print("Listing incoming videos...")
    files = list_files(api, prefix="incoming/")

    if not files:
        print("No videos to process.")
        return

    for file in files:
        file_name = file["fileName"]
        print(f"\nProcessing: {file_name}")

        local_input = "input.mp4"
        download_file(api, file_name, local_input)

        output_video = process_video(model, local_input)

        annotated_remote = f"processed/{os.path.basename(file_name)}"
        upload_file(api, output_video, annotated_remote)

        original_remote = f"processed/originals/{os.path.basename(file_name)}"
        upload_file(api, local_input, original_remote)

        print(f"Processed and uploaded: {annotated_remote}")

        shutil.rmtree(os.path.dirname(output_video), ignore_errors=True)
        os.remove(local_input)

    print("\nAll videos processed.")


if __name__ == "__main__":
    main()
