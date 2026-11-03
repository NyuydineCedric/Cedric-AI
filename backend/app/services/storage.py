"""
Cedric AI - File Storage
==========================

A small wrapper around "put a file on disk, read it back, delete it" -
scoped per user, so the filesystem layout mirrors the ownership rule
in the database (`storage/<user_id>/<uuid>.<ext>`).

WHY A SEPARATE MODULE INSTEAD OF INLINE IN THE ROUTE:
Local disk is the right choice for a single-machine dev setup, but a
real deployment (multiple backend instances, or just wanting durable
storage independent of the server's disk) would want S3 or similar
object storage instead. Keeping every filesystem call behind this one
module's functions means swapping the backing store later touches
only this file, not every route that handles documents.
"""

import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

# Extensions we actually know how to process later (Phase 5). Anything
# else is rejected at upload time rather than silently accepted and
# failing later when we try to extract text from it.
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".png", ".jpg", ".jpeg"}

MAX_UPLOAD_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024


class UploadValidationError(Exception):
    """Raised for a rejected upload - the route turns this into a 400."""


def _user_dir(user_id: int) -> Path:
    path = Path(settings.storage_dir) / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload(user_id: int, upload: UploadFile, contents: bytes) -> tuple[str, str, int]:
    """
    Persist an already-read file to disk for `user_id`.
    Returns (stored_filename, content_type, size_bytes).
    """
    original_name = upload.filename or "unnamed"
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Unsupported file type '{extension}'. Allowed: "
            f"{', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    if len(contents) > MAX_UPLOAD_SIZE_BYTES:
        raise UploadValidationError(
            f"File exceeds the {settings.max_upload_size_mb}MB upload limit."
        )

    if len(contents) == 0:
        raise UploadValidationError("Uploaded file is empty.")

    stored_filename = f"{uuid.uuid4().hex}{extension}"
    dest = _user_dir(user_id) / stored_filename
    dest.write_bytes(contents)

    content_type = upload.content_type or "application/octet-stream"
    return stored_filename, content_type, len(contents)


def resolve_path(user_id: int, stored_filename: str) -> Path:
    return _user_dir(user_id) / stored_filename


def delete_file(user_id: int, stored_filename: str) -> None:
    path = resolve_path(user_id, stored_filename)
    path.unlink(missing_ok=True)
