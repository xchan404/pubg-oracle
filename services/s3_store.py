"""
S3 storage helper for PUBG Oracle (R5).

Uses boto3. On EC2 the LabInstanceProfile provides credentials automatically;
locally, temporary lab credentials go in .env (never committed).

When S3_BUCKET is unset, every function logs a clear line and returns None/[]
so local dev keeps working without S3.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("pubg_s3")

S3_BUCKET = os.getenv("S3_BUCKET", "").strip()
AWS_REGION = os.getenv("AWS_REGION", "us-east-1").strip()


def _client():
    """Return a boto3 S3 client, or None when S3 is not configured."""
    if not S3_BUCKET:
        logger.info("[s3] S3_BUCKET not set — skipping S3 operation (local dev mode).")
        return None
    try:
        import boto3
        return boto3.client("s3", region_name=AWS_REGION)
    except Exception as e:
        logger.error("[s3] failed to create client: %s", e)
        return None


def configured() -> bool:
    return bool(S3_BUCKET)


def upload_file(local_path: str, key: str) -> Optional[str]:
    """Upload a local file to s3://BUCKET/key. Returns the key on success."""
    client = _client()
    if client is None:
        return None
    try:
        client.upload_file(local_path, S3_BUCKET, key)
        logger.info("[s3] uploaded %s -> s3://%s/%s", local_path, S3_BUCKET, key)
        return key
    except Exception as e:
        logger.error("[s3] upload failed (%s -> %s): %s", local_path, key, e)
        return None


def download_file(key: str, local_path: str) -> Optional[str]:
    """Download s3://BUCKET/key to local_path. Returns local_path on success."""
    client = _client()
    if client is None:
        return None
    try:
        client.download_file(S3_BUCKET, key, local_path)
        logger.info("[s3] downloaded s3://%s/%s -> %s", S3_BUCKET, key, local_path)
        return local_path
    except Exception as e:
        logger.error("[s3] download failed (%s -> %s): %s", key, local_path, e)
        return None


def list_versions(prefix: str = "") -> list:
    """List object versions under prefix (for T4 evidence)."""
    client = _client()
    if client is None:
        return []
    try:
        resp = client.list_object_versions(Bucket=S3_BUCKET, Prefix=prefix)
        versions = []
        for v in resp.get("Versions", []):
            versions.append({
                "key": v["Key"],
                "version_id": v["VersionId"],
                "last_modified": v["LastModified"].isoformat(),
                "size": v["Size"],
                "is_latest": v.get("IsLatest", False),
            })
        return versions
    except Exception as e:
        logger.error("[s3] list_versions failed: %s", e)
        return []


def generate_presigned_url(key: str, expiry_seconds: int = 300) -> Optional[str]:
    """Generate a short-lived presigned GET URL for a key."""
    client = _client()
    if client is None:
        return None
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expiry_seconds,
        )
        return url
    except Exception as e:
        logger.error("[s3] presigned url failed (%s): %s", key, e)
        return None
