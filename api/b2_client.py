import os
from b2sdk.v2 import B2Api, InMemoryAccountInfo

def get_b2_client():
    account_info = InMemoryAccountInfo()
    b2_api = B2Api(account_info)

    b2_api.authorize_account(
        "production",
        os.getenv("B2_KEY_ID"),
        os.getenv("B2_APP_KEY")
    )

    return b2_api


def upload_bytes(path: str, data: bytes, content_type: str):
    b2_api = get_b2_client()
    bucket = b2_api.get_bucket_by_name(os.getenv("B2_BUCKET_NAME"))

    bucket.upload_bytes(
        data,
        file_name=path,
        content_type=content_type
    )


def download_bytes(path: str) -> bytes:
    b2_api = get_b2_client()
    bucket = b2_api.get_bucket_by_name(os.getenv("B2_BUCKET_NAME"))

    file_info, file_stream = bucket.download_file_by_name(path)
    return file_stream.read()


def move_file(old_path: str, new_path: str):
    b2_api = get_b2_client()
    bucket = b2_api.get_bucket_by_name(os.getenv("B2_BUCKET_NAME"))

    file_info, _ = bucket.download_file_by_name(old_path)

    bucket.copy(
        file_info.id_,
        new_file_name=new_path,
        destination_bucket=bucket
    )

    bucket.delete_file_version(file_info.id_, old_path)


def list_prefix(prefix: str):
    b2_api = get_b2_client()
    bucket = b2_api.get_bucket_by_name(os.getenv("B2_BUCKET_NAME"))

    return list(bucket.ls(prefix=prefix))
