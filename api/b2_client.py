import os
from b2sdk.v2 import B2Api, InMemoryAccountInfo

B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APP_KEY = os.getenv("B2_APP_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")

account_info = InMemoryAccountInfo()
b2_api = B2Api(account_info)
b2_api.authorize_account("production", B2_KEY_ID, B2_APP_KEY)
bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)


def upload_bytes(path: str, data: bytes, content_type: str):
    bucket.upload_bytes(
        data,
        file_name=path,
        content_type=content_type
    )


def download_bytes(path: str) -> bytes:
    file_info, file_stream = bucket.download_file_by_name(path)
    return file_stream.read()


def move_file(old_path: str, new_path: str):
    file_info, _ = bucket.download_file_by_name(old_path)
    bucket.copy(
        file_info.id_,
        new_file_name=new_path,
        destination_bucket=bucket
    )
    bucket.delete_file_version(file_info.id_, old_path)


def list_prefix(prefix: str):
    return list(bucket.ls(prefix=prefix))
