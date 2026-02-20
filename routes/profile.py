from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    jsonify,
)

from database import models
from services.image_upload import save_profile_image


bp = Blueprint("profile", __name__, url_prefix="/profile")


# ---------------------------
# LOGIN GUARD
# ---------------------------
def _require_login():
    if not session.get("user_id"):
        flash("Please login to continue.", "error")
        return redirect(url_for("auth.login_get"))
    return None


# ---------------------------
# EDIT PROFILE (HTML FORM)
# ---------------------------
@bp.get("/edit")
def edit_profile():
    guard = _require_login()
    if guard:
        return guard

    db_path = current_app.config["DB_PATH"]
    profile = models.get_profile_by_user_id(db_path, int(session["user_id"]))
    return render_template("profile_form.html", profile=profile)


@bp.post("/edit")
def save_profile():
    guard = _require_login()
    if guard:
        return guard

    db_path = current_app.config["DB_PATH"]
    user_id = int(session["user_id"])

    def get_int(name: str, default: int = 0) -> int:
        try:
            return int(request.form.get(name) or default)
        except Exception:
            return default

    full_name = (request.form.get("full_name") or "").strip()
    age = get_int("age")
    gender = (request.form.get("gender") or "").strip()

    if not full_name:
        flash("Full name is required.", "error")
        return redirect(url_for("profile.edit_profile"))
    if age < 18 or age > 80:
        flash("Age must be between 18 and 80.", "error")
        return redirect(url_for("profile.edit_profile"))
    if gender not in {"Male", "Female", "Other"}:
        flash("Please select a valid gender.", "error")
        return redirect(url_for("profile.edit_profile"))

    existing = models.get_profile_by_user_id(db_path, user_id) or {}
    image_filename = existing.get("image_filename")

    file = request.files.get("profile_image") if request.files else None
    if file is not None and file.filename == "":
        file = None

    try:
        uploaded = save_profile_image(
            file,
            upload_folder=current_app.config["UPLOAD_FOLDER"],
            allowed_exts=current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
        )
        if uploaded:
            image_filename = uploaded
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("profile.edit_profile"))
    except Exception:
        current_app.logger.exception("Profile image upload failed")
        flash("Image upload failed. Please try again.", "error")
        return redirect(url_for("profile.edit_profile"))

    profile_data = {
        "full_name": full_name,
        "age": age,
        "gender": gender,
        "height_cm": get_int("height_cm", 0) or None,
        "marital_status": (request.form.get("marital_status") or "").strip(),
        "location": (request.form.get("location") or "").strip(),
        "highest_education": (request.form.get("highest_education") or "").strip(),
        "occupation": (request.form.get("occupation") or "").strip(),
        "income_range": (request.form.get("income_range") or "").strip(),
        "smoking": (request.form.get("smoking") or "").strip(),
        "drinking": (request.form.get("drinking") or "").strip(),
        "medical_conditions": (request.form.get("medical_conditions") or "").strip(),
        "fitness_level": (request.form.get("fitness_level") or "").strip(),
        "pref_age_min": get_int("pref_age_min", 18),
        "pref_age_max": get_int("pref_age_max", 80),
        "pref_location": (request.form.get("pref_location") or "").strip(),
        "pref_education_level": (request.form.get("pref_education_level") or "").strip(),
        "image_filename": image_filename,
    }

    models.upsert_profile(db_path, user_id, profile_data)
    flash("Profile saved.", "success")
    return redirect(url_for("match.dashboard"))


# ---------------------------------------------------
# ✅ VIEW PROFILE ROUTE (THIS WAS MISSING)
# ---------------------------------------------------
@bp.get("/<int:profile_id>")
def view_profile(profile_id: int):
    guard = _require_login()
    if guard:
        return guard

    db_path = current_app.config["DB_PATH"]
    profile = models.get_profile_by_id(db_path, profile_id)

    if not profile:
        flash("Profile not found.", "error")
        return redirect(url_for("match.dashboard"))

    return render_template("profile_view.html", target=profile)


# ---------------------------------------------------
# API IMAGE UPLOAD (ANDROID)
# ---------------------------------------------------
@bp.route("/api/upload_profile_image", methods=["POST"])
def api_upload_profile_image():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = int(session["user_id"])
    db_path = current_app.config["DB_PATH"]

    if not request.files:
        return jsonify({"error": "No file received"}), 400

    file = next(iter(request.files.values()))
    if not file or file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    try:
        filename = save_profile_image(
            file,
            upload_folder=current_app.config["UPLOAD_FOLDER"],
            allowed_exts=current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
        )
        if not filename:
            return jsonify({"error": "No file received"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("API profile image upload failed")
        return jsonify({"error": "Upload failed"}), 500

    if not models.update_profile_image(db_path, user_id, filename):
        return jsonify({"error": "Profile not found. Create profile first."}), 400

    return jsonify({"success": True, "image_url": f"/static/uploads/{filename}"})