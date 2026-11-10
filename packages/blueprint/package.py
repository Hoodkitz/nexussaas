"""Deterministic packaging: identical inputs produce a byte-identical zip (same sha256)."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile

FIXED_DATE = (2020, 1, 1, 0, 0, 0)


def build_zip(files: dict[str, str], root: str) -> tuple[bytes, str]:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(files):
            info = zipfile.ZipInfo(f"{root}/{rel}", date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[rel].encode("utf-8"))
    data = buf.getvalue()
    return data, hashlib.sha256(data).hexdigest()


def manifest(files: dict[str, str], extra: dict) -> str:
    entries = {rel: hashlib.sha256(files[rel].encode()).hexdigest() for rel in sorted(files)}
    return json.dumps({**extra, "files": entries}, indent=2, sort_keys=True) + "\n"
