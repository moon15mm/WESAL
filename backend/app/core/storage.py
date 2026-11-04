"""Secure file storage on a local (Docker volume) disk.

- Content type is detected from the bytes (libmagic), never trusted from the client.
- Only whitelisted types per purpose; size limits enforced while streaming.
- Images are re-encoded with Pillow (strips EXIF/GPS metadata and embedded payloads).
- Files are stored under random keys outside the web root; private files are served
  only through authorized API endpoints.
"""
from __future__ import annotations

import io
import secrets
from pathlib import Path

import magic
from fastapi import UploadFile
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ValidationFailed
from app.core.security import sha256_hex
from app.models.business import StoredFile
from app.models.enums import FilePurpose

IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
DOC_TYPES = {**IMAGE_TYPES, "application/pdf": "pdf"}

ALLOWED: dict[FilePurpose, dict[str, str]] = {
    FilePurpose.product_image: IMAGE_TYPES,
    FilePurpose.business_logo: IMAGE_TYPES,
    FilePurpose.avatar: IMAGE_TYPES,
    FilePurpose.ad_banner: IMAGE_TYPES,
    FilePurpose.business_document: DOC_TYPES,
    FilePurpose.rep_document: DOC_TYPES,
    FilePurpose.delivery_proof: DOC_TYPES,
    FilePurpose.return_evidence: DOC_TYPES,
    FilePurpose.payment_proof: DOC_TYPES,
    FilePurpose.invoice: DOC_TYPES,
    FilePurpose.complaint_attachment: DOC_TYPES,
}
PUBLIC_PURPOSES = {FilePurpose.product_image, FilePurpose.business_logo, FilePurpose.ad_banner}
MAX_IMAGE_SIDE = 1600

Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression bomb guard


def storage_root() -> Path:
    root = Path(settings.storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _read_limited(upload: UploadFile) -> bytes:
    limit = settings.max_upload_mb * 1024 * 1024
    buf = io.BytesIO()
    while chunk := upload.file.read(1024 * 256):
        buf.write(chunk)
        if buf.tell() > limit:
            raise ValidationFailed("file_too_large", params={"max_mb": settings.max_upload_mb})
    return buf.getvalue()


def _sanitize_image(data: bytes, mime: str) -> tuple[bytes, str, int, int]:
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
    except Exception:
        raise ValidationFailed("file_invalid_image")
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    out = io.BytesIO()
    if mime == "image/png" and img.mode in ("RGBA", "LA", "P"):
        img.save(out, format="PNG", optimize=True)
        mime = "image/png"
    else:
        img = img.convert("RGB")
        img.save(out, format="WEBP", quality=82, method=4)
        mime = "image/webp"
    return out.getvalue(), mime, img.width, img.height


def _check_pdf(data: bytes) -> None:
    head = data[:2048]
    if not data.startswith(b"%PDF-"):
        raise ValidationFailed("file_type_not_allowed")
    # reject PDFs with active content
    lowered = data.lower()
    for marker in (b"/javascript", b"/js ", b"/launch", b"/embeddedfile"):
        if marker in lowered:
            raise ValidationFailed("file_unsafe_content")
    del head


def save_upload(
    db: Session,
    upload: UploadFile,
    purpose: FilePurpose,
    *,
    owner_user_id=None,
    business_id=None,
) -> StoredFile:
    data = _read_limited(upload)
    if not data:
        raise ValidationFailed("file_empty")
    return save_bytes(db, data, upload.filename or "file", purpose, owner_user_id=owner_user_id, business_id=business_id)


def save_bytes(db: Session, data: bytes, filename: str, purpose: FilePurpose, *, owner_user_id=None, business_id=None) -> StoredFile:
    mime = magic.from_buffer(data[:4096], mime=True)
    allowed = ALLOWED[purpose]
    if mime not in allowed:
        raise ValidationFailed("file_type_not_allowed", params={"type": mime})
    width = height = None
    if mime in IMAGE_TYPES:
        data, mime, width, height = _sanitize_image(data, mime)
    elif mime == "application/pdf":
        _check_pdf(data)
    ext = DOC_TYPES.get(mime, "bin")
    key = f"{purpose.value}/{secrets.token_hex(2)}/{secrets.token_urlsafe(24)}.{ext}"
    path = storage_root() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")[:200] or f"file.{ext}"
    record = StoredFile(
        owner_user_id=owner_user_id,
        business_id=business_id,
        purpose=purpose,
        storage_key=key,
        original_name=safe_name,
        mime_type=mime,
        size_bytes=len(data),
        sha256=sha256_hex(data),
        is_public=purpose in PUBLIC_PURPOSES,
        width=width,
        height=height,
    )
    db.add(record)
    db.flush()
    return record


def file_path(record: StoredFile) -> Path:
    path = (storage_root() / record.storage_key).resolve()
    if storage_root() not in path.parents:
        raise ValidationFailed("file_invalid_path")
    return path
