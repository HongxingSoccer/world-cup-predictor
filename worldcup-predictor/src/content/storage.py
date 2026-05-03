"""S3 / MinIO upload wrapper used by `CardGenerator`.

`build_card_storage()` reads `settings.S3_*` and either returns a working
`CardStorage` (when `S3_ENDPOINT` is non-empty) or `NullCardStorage` —
a degraded-mode shim that logs and returns a `data:` URL so local dev keeps
working without MinIO running.
"""
from __future__ import annotations

from typing import Protocol

import structlog

from src.config.settings import settings

logger = structlog.get_logger(__name__)


class CardStorage(Protocol):
    """Minimal contract every storage backend honours."""

    def upload_png(self, key: str, body: bytes) -> str: ...

    def public_url(self, key: str) -> str: ...


class _S3CardStorage:
    """boto3-backed S3 / MinIO uploader."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
        public_base_url: str,
    ) -> None:
        # Lazy import keeps boto3 out of unrelated test fast-paths.
        import boto3
        from botocore.client import Config

        self._bucket = bucket
        self._public_base_url = (public_base_url or endpoint).rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            # MinIO requires path-style addressing; S3 happily accepts both.
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self._ensure_bucket()

    def upload_png(self, key: str, body: bytes) -> str:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType="image/png",
            CacheControl="public, max-age=31536000, immutable",
        )
        url = self.public_url(key)
        logger.info("card_uploaded", bucket=self._bucket, key=key, bytes=len(body))
        return url

    def public_url(self, key: str) -> str:
        return f"{self._public_base_url}/{self._bucket}/{key}"

    def _ensure_bucket(self) -> None:
        # Cheap idempotent check — head_bucket → 404 → create.
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            try:
                self._client.create_bucket(Bucket=self._bucket)
                logger.info("card_bucket_created", bucket=self._bucket)
            except Exception as exc:
                logger.warning("card_bucket_create_failed", error=str(exc))


class NullCardStorage:
    """No-op fallback. Returns a `data:image/png;base64,…` URL so local dev keeps working."""

    def upload_png(self, key: str, body: bytes) -> str:
        import base64

        b64 = base64.b64encode(body).decode("ascii")
        url = f"data:image/png;base64,{b64[:48]}…"  # truncated for log noise
        logger.info("card_storage_noop", key=key, bytes=len(body))
        return url

    def public_url(self, key: str) -> str:
        return f"local://{key}"


def build_card_storage() -> CardStorage:
    """Pick the storage backend based on `settings.S3_ENDPOINT`."""
    if not settings.S3_ENDPOINT:
        return NullCardStorage()
    return _S3CardStorage(
        endpoint=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY,
        bucket=settings.S3_BUCKET_CARDS,
        region=settings.S3_REGION,
        public_base_url=settings.S3_PUBLIC_BASE_URL,
    )
