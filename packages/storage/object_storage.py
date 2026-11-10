"""Object storage for large artifacts (ADR-03). Graph state only keeps keys + hashes.

Backends: ``local`` (filesystem, dev) and ``s3`` (any S3-compatible store, e.g. MinIO).
Keys are always prefixed ``tenants/<tenant_id>/`` by callers.
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

from packages.settings import settings

_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,500}$")


def _check_key(key: str) -> str:
    if not _KEY_RE.match(key) or ".." in key.split("/"):
        raise ValueError(f"invalid object key: {key!r}")
    return key


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / _check_key(key)).resolve()
        if self.root not in p.parents:
            raise ValueError("key escapes storage root")
        return p

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)
        return {"key": key, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def delete_prefix(self, prefix: str) -> int:
        base = self._path(prefix.rstrip("/"))
        n = 0
        if base.is_dir():
            for f in sorted(base.rglob("*"), reverse=True):
                if f.is_file():
                    f.unlink()
                    n += 1
                else:
                    f.rmdir()
            base.rmdir()
        return n

    def healthy(self) -> bool:
        return self.root.is_dir()


class S3Storage:
    def __init__(self):
        import boto3

        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3", endpoint_url=settings.S3_ENDPOINT or None,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
        )

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
        digest = hashlib.sha256(data).hexdigest()
        self.client.put_object(Bucket=self.bucket, Key=_check_key(key), Body=data, ContentType=content_type,
                               Metadata={"sha256": digest}, ServerSideEncryption="AES256")
        return {"key": key, "sha256": digest, "size": len(data)}

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=_check_key(key))["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=_check_key(key))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=_check_key(key))

    def delete_prefix(self, prefix: str) -> int:
        n = 0
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=_check_key(prefix)):
            objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if objs:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": objs})
                n += len(objs)
        return n

    def healthy(self) -> bool:
        self.client.head_bucket(Bucket=self.bucket)
        return True


@lru_cache
def get_storage():
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage()
    return LocalStorage(settings.STORAGE_LOCAL_DIR)


def tenant_prefix(tenant_id) -> str:
    return f"tenants/{tenant_id}/"
