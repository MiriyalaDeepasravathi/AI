import os
from pathlib import Path


class Config:
    """Base configuration.

    Notes:
    - Uses SQLite by default.
    - Uploads are stored under `static/uploads/`.
    """

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # Admin is determined dynamically:
    # a normal user becomes admin if their email equals ADMIN_EMAIL.
    ADMIN_EMAIL = (os.environ.get("ADMIN_EMAIL") or "admin@matrimony.local").strip().lower()

    BASE_DIR = Path(__file__).resolve().parent
    # IMPORTANT: The app uses the existing SQLite file at `database/matrimony.db`.
    # Match scores are computed dynamically and are not stored.
    DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "database" / "matrimony.db"))

    # NOTE: Keep this as a simple relative default so it works in different deploy layouts.
    # `create_app()` normalizes it to an absolute path under `app.root_path`.
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "static/uploads")
    # Mobile photos (especially iOS) can exceed 5MB easily.
    # Keep a reasonable default and allow override via env.
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 15 * 1024 * 1024))  # 15MB

    # Images allowed for profile uploads.
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
