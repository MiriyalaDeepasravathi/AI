from __future__ import annotations

import secrets
from pathlib import Path
from typing import Iterable, Optional

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


def allowed_file(filename: str, allowed_exts: Iterable[str]) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in {e.lower() for e in allowed_exts}


_MIMETYPE_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}


def _guess_ext(file: FileStorage) -> Optional[str]:
    if file.filename and "." in file.filename:
        return secure_filename(file.filename).rsplit(".", 1)[1].lower()
    mt = (file.mimetype or "").lower().split(";")[0].strip()
    return _MIMETYPE_TO_EXT.get(mt)


def _require_image(file: FileStorage) -> None:
    mt = (file.mimetype or "").lower()
    # Some clients may not send a reliable mimetype; don't block uploads solely on that.
    if mt and not mt.startswith("image/"):
        raise ValueError("Invalid file. Please upload an image.")


def _convert_heic_to_jpeg(file: FileStorage, dest: Path) -> None:
    # Optional dependency: pillow + pillow-heif
    try:
        from PIL import Image, ImageOps  # type: ignore
        import pillow_heif  # type: ignore

        pillow_heif.register_heif_opener()
        file.stream.seek(0)
        img = Image.open(file.stream)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, format="JPEG", quality=88, optimize=True)
        file.stream.seek(0)
    except Exception as e:
        raise ValueError(
            "This photo format (HEIC/HEIF) isn't supported on the server yet. "
            "Please upload a JPG/PNG/WebP image (or change your phone camera setting to 'Most Compatible')."
        ) from e


def save_profile_image(
    file: Optional[FileStorage],
    upload_folder: str,
    allowed_exts: Iterable[str],
) -> Optional[str]:
    """Securely save a profile image and return stored filename.

    - Uses Werkzeug's `secure_filename`
    - Adds a random token to avoid collisions
    - Restricts extensions to configured allowed types

    Note: This demo does not do deep content inspection.
    For production, consider validating MIME type and decoding via Pillow.
    """
    if not file or not file.filename:
        return None

    _require_image(file)

    ext = _guess_ext(file)
    if not ext or ext.lower() not in {e.lower() for e in allowed_exts}:
        raise ValueError("Invalid image type. Please upload PNG/JPG/JPEG/GIF.")

    token = secrets.token_hex(8)
    # Store with the validated extension.
    stored_ext = ext
    stored_name = f"profile_{token}.{stored_ext}"

    folder = Path(upload_folder)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / stored_name

    file.save(dest)

    return stored_name


def save_message_attachment(
    file: Optional[FileStorage],
    upload_folder: str,
    allowed_exts: Iterable[str],
) -> Optional[str]:
    """Securely save a message attachment and return stored filename.

    Images-first: caller should restrict `allowed_exts` to web-safe image types.
    This function is intentionally light (no heavy MIME sniffing) to keep
    dependencies minimal.
    """
    if not file or not file.filename:
        return None

    original = secure_filename(file.filename)
    if not allowed_file(original, allowed_exts):
        raise ValueError("Invalid attachment type.")

    ext = original.rsplit(".", 1)[1].lower()
    token = secrets.token_hex(8)
    stored_name = f"msg_{token}.{ext}"

    folder = Path(upload_folder)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / stored_name
    file.save(dest)

    return stored_name
