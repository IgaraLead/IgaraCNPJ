"""
S3-compatible object storage (MinIO) client.

Provides helpers to upload files and generate presigned download URLs.
All processed export files (CSV/XLSX) are stored here permanently.
"""

import os
import logging

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "processed-files")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

# Presigned URL lifetime (1 hour is plenty — the user can always re-generate)
PRESIGN_EXPIRY = int(os.getenv("S3_PRESIGN_EXPIRY", "3600"))

_client = None


def _get_client():
    """Lazy-init the boto3 S3 client."""
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name=S3_REGION,
            config=Config(signature_version="s3v4"),
        )
        _ensure_bucket()
    return _client


def _ensure_bucket():
    """Create the bucket if it doesn't exist yet."""
    client = _client  # already initialised at this point
    try:
        client.head_bucket(Bucket=S3_BUCKET)
    except ClientError:
        try:
            client.create_bucket(Bucket=S3_BUCKET)
            logger.info("Created S3 bucket: %s", S3_BUCKET)
        except ClientError as e:
            logger.error("Failed to create S3 bucket %s: %s", S3_BUCKET, e)
            raise


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream"):
    """Upload raw bytes to S3."""
    client = _get_client()
    client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    logger.info("Uploaded %s (%d bytes) to s3://%s", key, len(data), S3_BUCKET)


def upload_file(key: str, file_path: str, content_type: str = "application/octet-stream"):
    """Upload a local file to S3."""
    client = _get_client()
    client.upload_file(
        file_path,
        S3_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    logger.info("Uploaded %s to s3://%s", key, S3_BUCKET)


def presigned_url(key: str, filename: str | None = None, expiry: int = PRESIGN_EXPIRY) -> str:
    """Generate a presigned GET URL for an object."""
    client = _get_client()
    params: dict = {"Bucket": S3_BUCKET, "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expiry,
    )


def object_exists(key: str) -> bool:
    """Check if an object exists in the bucket."""
    client = _get_client()
    try:
        client.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def get_object_body(key: str):
    """Return a streaming body for an S3 object (iterable of bytes)."""
    client = _get_client()
    response = client.get_object(Bucket=S3_BUCKET, Key=key)
    return response["Body"].iter_chunks(chunk_size=64 * 1024)


def delete_object(key: str):
    """Delete an object from the bucket."""
    client = _get_client()
    client.delete_object(Bucket=S3_BUCKET, Key=key)
