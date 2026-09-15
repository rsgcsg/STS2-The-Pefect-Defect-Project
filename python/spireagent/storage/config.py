"""Application storage selection; no UI, model, or vendor-specific callers."""
import os
from pathlib import Path

from ..json_boundary import BoundaryError
from .local import LocalBlobStore
from .s3 import S3BlobStore, S3Config
from .store import ManifestArtifactStore


def open_store(location: str) -> ManifestArtifactStore:
    """'s3' selects environment configuration; every other value is a local directory."""
    if location == "s3":
        bucket = os.environ.get("STPD_S3_BUCKET")
        if not bucket:
            raise BoundaryError("configuration", "missing_s3_bucket")
        config = S3Config(
            bucket=bucket,
            endpoint=os.environ.get("STPD_S3_ENDPOINT") or None,
            prefix=os.environ.get("STPD_S3_PREFIX", "stpd"),
            region=os.environ.get("STPD_S3_REGION", "us-east-1"),
        )
        return ManifestArtifactStore(S3BlobStore(config))
    return ManifestArtifactStore(LocalBlobStore(Path(location)))
