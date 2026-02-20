from __future__ import annotations

import os

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge

from config import Config
from database import models
from routes import admin, auth, interest, match, messages, profile


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Enable CORS
    CORS(app, supports_credentials=True)

    # Ensure upload folder exists (Railway-safe): normalize to absolute path.
    upload_folder = app.config.get("UPLOAD_FOLDER") or "static/uploads"
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(app.root_path, upload_folder)
    app.config["UPLOAD_FOLDER"] = upload_folder
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Init DB tables
    models.init_db(app.config["DB_PATH"])

    if hasattr(models, "migrate_db"):
        models.migrate_db(app.config["DB_PATH"])

    # Blueprints
    app.register_blueprint(auth.bp)
    app.register_blueprint(profile.bp)
    app.register_blueprint(match.bp)
    app.register_blueprint(interest.bp)
    app.register_blueprint(messages.bp)
    app.register_blueprint(admin.bp)

    # ==============================
    # 🔥 NEW API FOR MIT APP UPLOAD
    # ==============================
    @app.route("/api/upload_profile_image", methods=["POST"])
    def api_upload_profile_image():
        from services.image_upload import save_profile_image

        file = request.files.get("profile_image") or request.files.get("file")
        if not file:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        if file.filename == "":
            return jsonify({"status": "error", "message": "Empty filename"}), 400

        try:
            filename = save_profile_image(
                file,
                upload_folder=app.config["UPLOAD_FOLDER"],
                allowed_exts=app.config["ALLOWED_IMAGE_EXTENSIONS"],
            )
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        except Exception:
            app.logger.exception("API image upload failed")
            return jsonify({"status": "error", "message": "Upload failed"}), 500

        return jsonify({"status": "success", "image_url": f"/static/uploads/{filename}"}), 200

    # ==============================

    @app.context_processor
    def inject_is_admin():
        try:
            from flask import session

            user_id = session.get("user_id")
            if not user_id:
                return {"is_admin": False}

            user = models.get_user_by_id(
                app.config["DB_PATH"],
                int(user_id)
            )
            return {
                "is_admin": bool(
                    user and user.get("email") == app.config.get("ADMIN_EMAIL")
                )
            }
        except Exception:
            return {"is_admin": False}

    @app.after_request
    def add_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        return resp

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(e):
        from flask import flash, redirect, request, url_for

        max_mb = int(app.config.get("MAX_CONTENT_LENGTH", 0) or 0) // (1024 * 1024)
        flash(f"Upload too large. Please choose a smaller image (max {max_mb}MB).", "error")
        return redirect(request.referrer or url_for("profile.edit_profile"))

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)