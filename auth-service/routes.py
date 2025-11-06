import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import jwt
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from models import db, User, UserProfile

ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
AVATAR_DIR = "uploads/avatars"

bp = Blueprint("auth", __name__, url_prefix="/auth")
SECRET = os.getenv("JWT_SECRET", "devsecret")


def normalize_email(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower()


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if digits.startswith("84"):
        digits = "0" + digits[2:]
    elif digits.startswith("084"):
        digits = "0" + digits[3:]
    return digits or None


def _decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_sub": False})


def _make_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "approved": user.approved,
        "locked": user.locked,
        "exp": datetime.utcnow() + timedelta(hours=6),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _require_admin():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, ({"error": "no_token"}, 401)
    token = auth_header.split(" ", 1)[1]
    try:
        payload = _decode_token(token)
    except Exception:
        return None, ({"error": "invalid_token"}, 401)
    if payload.get("role") != "admin":
        return None, ({"error": "forbidden"}, 403)
    return payload, None


def _require_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, ({"error": "no_token"}, 401)
    token = auth_header.split(" ", 1)[1]
    try:
        payload = _decode_token(token)
    except Exception:
        return None, ({"error": "invalid_token"}, 401)

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None, ({"error": "invalid_subject"}, 401)

    user = User.query.get(user_id)
    if not user:
        return None, ({"error": "user_not_found"}, 404)
    if user.locked:
        return None, ({"error": "locked"}, 403)
    if user.role != "admin" and not user.approved:
        return None, ({"error": "not_approved"}, 403)
    return user, None


def _save_avatar(file_storage):
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None, "no_file"

    filename = secure_filename(file_storage.filename)
    if "." not in filename:
        return None, "bad_filename"

    extension = filename.rsplit(".", 1)[-1].lower()
    if extension not in ALLOWED_IMAGE_EXTS:
        return None, "unsupported_type"

    destination = Path(current_app.static_folder) / AVATAR_DIR
    destination.mkdir(parents=True, exist_ok=True)

    new_name = f"{uuid.uuid4().hex}.{extension}"
    file_storage.save(destination / new_name)
    return new_name, None


@bp.get("/")
def health():
    return {"service": "auth", "status": "ok", "prefix": "/auth"}


@bp.get("/lookup")
def lookup_user():
    """Public lookup for basic user info by username/email/phone.
    Returns minimal fields: id, username, email, role, approved, locked.
    """
    identifier = (request.args.get("username") or request.args.get("email") or request.args.get("phone") or "").strip()
    if not identifier:
        return {"error": "missing_identifier"}, 400

    user = None
    if "@" in identifier:
        user = User.query.filter_by(email=identifier.lower()).first()
    elif identifier.isdigit():
        # simple phone normalize
        digits = re.sub(r"\D", "", identifier)
        if digits.startswith("84"):
            digits = "0" + digits[2:]
        elif digits.startswith("084"):
            digits = "0" + digits[3:]
        user = User.query.filter_by(phone=digits).first()
    else:
        user = User.query.filter_by(username=identifier).first()

    if not user:
        return {"error": "not_found"}, 404

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "approved": user.approved,
        "locked": user.locked,
    }, 200


@bp.post("/register")
def register():
    data = request.get_json(force=True) if request.is_json else request.form
    username = (data.get("username") or "").strip()
    email = normalize_email(data.get("email"))
    phone = normalize_phone(data.get("phone"))
    password = data.get("password") or ""

    if not username or not email or not password:
        return {"error": "missing_fields"}, 400

    conditions = [User.username == username, User.email == email]
    if phone:
        conditions.append(User.phone == phone)

    existing = User.query.filter(or_(*conditions)).first()
    if existing:
        if existing.username == username:
            return {"error": "username_exists"}, 409
        if existing.email == email:
            return {"error": "email_exists"}, 409
        if phone and existing.phone == phone:
            return {"error": "phone_exists"}, 409

    user = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        role="member",
        approved=False,
        locked=False,
        phone=phone,
    )
    db.session.add(user)
    db.session.commit()
    return {"id": user.id, "username": user.username}, 201


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    payload = request.get_json(force=True) if request.is_json else request.form
    identifier = (
        payload.get("username")
        or payload.get("identifier")
        or payload.get("email")
        or ""
    ).strip()
    password = payload.get("password") or ""

    if not identifier or not password:
        if request.is_json:
            return {"error": "missing_fields"}, 400
        flash("Vui lòng nhập đầy đủ thông tin!", "error")
        return redirect(url_for("auth.login"))

    if "@" in identifier:
        user = User.query.filter_by(email=identifier.lower()).first()
    elif identifier.isdigit():
        user = User.query.filter_by(phone=normalize_phone(identifier)).first()
    else:
        user = User.query.filter_by(username=identifier).first()

    if not user or not check_password_hash(user.password, password):
        if request.is_json:
            return {"error": "invalid_credentials"}, 401
        flash("Tên đăng nhập hoặc mật khẩu không đúng!", "error")
        return redirect(url_for("auth.login"))

    if user.locked:
        if request.is_json:
            return {"error": "locked"}, 403
        flash("Tài khoản của bạn đã bị khóa!", "error")
        return redirect(url_for("auth.login"))

    if user.role != "admin" and not user.approved:
        if request.is_json:
            return {"error": "not_approved"}, 403
        flash("Tài khoản chưa được admin duyệt!", "error")
        return redirect(url_for("auth.login"))

    token = _make_token(user)

    if request.is_json:
        return {"access_token": token, "role": user.role}

    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role
    flash("Đăng nhập thành công!", "success")

    return redirect(url_for("auth.admin_list_users" if user.role == "admin" else "auth.profile_page"))


@bp.get("/login_page")
def login_page():
    return render_template("login.html")


@bp.get("/me")
def me():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {"error": "no_token"}, 401
    try:
        payload = _decode_token(auth_header.split(" ", 1)[1])
    except Exception:
        return {"error": "invalid_token"}, 401
    return payload


@bp.get("/admin/users")
def admin_list_users():
    _, error = _require_admin()
    if error:
        return error

    users = User.query.order_by(User.id.desc()).all()
    data = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_admin": user.role == "admin",
            "approved": user.approved,
            "locked": user.locked,
            "created_at": user.created_at.isoformat(),
        }
        for user in users
    ]
    return {"data": data}


@bp.patch("/users/<int:user_id>/status")
def update_status(user_id: int):
    _, error = _require_admin()
    if error:
        return error

    data = request.get_json(force=True)
    status = (data.get("status") or "pending").lower()

    user = User.query.get_or_404(user_id)
    if status == "approved":
        user.approved, user.locked = True, False
    elif status == "locked":
        user.approved, user.locked = False, True
    else:
        user.approved, user.locked = False, False

    db.session.commit()
    return {"ok": True, "status": status}


@bp.get("/profile")
def get_profile():
    user, error = _require_user()
    if error:
        return error

    profile = UserProfile.query.filter_by(user_id=user.id).first()
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.session.add(profile)
        db.session.commit()

    return {"user": user.to_dict_basic(), "profile": profile.to_dict()}


@bp.put("/profile")
def update_profile():
    user, error = _require_user()
    if error:
        return error

    data = request.get_json(force=True)
    profile = UserProfile.query.filter_by(user_id=user.id).first()
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.session.add(profile)

    if "full_name" in data:
        profile.full_name = data.get("full_name") or None
    if "address" in data:
        profile.address = data.get("address") or None
    if "gender" in data:
        profile.gender = data.get("gender") or None
    if "vehicle_info" in data:
        profile.vehicle_info = data.get("vehicle_info") or None
    if "battery_info" in data:
        profile.battery_info = data.get("battery_info") or None
    if "birthdate" in data:
        raw = data.get("birthdate")
        if raw:
            try:
                profile.birthdate = datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                return {"error": "invalid_birthdate_format"}, 400
        else:
            profile.birthdate = None
    if "phone" in data:
        user.phone = normalize_phone(data.get("phone"))

    db.session.commit()
    return {"ok": True, "profile": profile.to_dict(), "user": user.to_dict_basic()}


@bp.post("/profile")
def update_profile_form():
    user, error = _require_user()
    if error:
        current_app.logger.error(f"[PROFILE] Auth error: {error}")
        return error

    profile = UserProfile.query.filter_by(user_id=user.id).first()
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.session.add(profile)

    form = request.form
    if form.get("full_name"):
        profile.full_name = form.get("full_name")
    if form.get("address"):
        profile.address = form.get("address")
    if form.get("vehicle_info"):
        profile.vehicle_info = form.get("vehicle_info")
    if form.get("battery_info"):
        profile.battery_info = form.get("battery_info")
    if form.get("gender"):
        profile.gender = form.get("gender")

    birthdate = form.get("birthdate")
    if birthdate:
        try:
            profile.birthdate = datetime.strptime(birthdate, "%Y-%m-%d").date()
        except ValueError:
            current_app.logger.warning("Invalid birthdate format provided; keeping previous value.")

    if form.get("phone") is not None:
        user.phone = normalize_phone(form.get("phone"))

    avatar_file = request.files.get("avatar")
    if avatar_file and avatar_file.filename:
        filename, upload_error = _save_avatar(avatar_file)
        if not upload_error:
            profile.avatar_url = filename

    db.session.commit()

    avatar_src = (
        url_for("static", filename=f"{AVATAR_DIR}/{profile.avatar_url}")
        if profile.avatar_url
        else url_for("static", filename="img/avatar-placeholder.png")
    )

    return {
        "ok": True,
        "profile": profile.to_dict(),
        "user": user.to_dict_basic(),
        "avatar_src": avatar_src,
    }


@bp.get("/profile-page", endpoint="profile_html")
def profile_html():
    return render_template("profile.html")


@bp.get("/profile/view")
def profile_page():
    user_id = session.get("user_id")
    user = User.query.get(user_id)
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if profile is None:
        profile = SimpleNamespace(
            full_name="",
            phone="",
            address="",
            gender="",
            birthdate="",
            vehicle_info="",
            battery_info="",
            avatar_url="",
        )

    raw_avatar = getattr(profile, "avatar_url", "") or ""
    if raw_avatar.startswith(("http://", "https://", "/")):
        avatar_src = raw_avatar
    elif raw_avatar:
        avatar_src = url_for("static", filename=f"{AVATAR_DIR}/{raw_avatar}")
    else:
        avatar_src = url_for("static", filename="img/avatar-placeholder.png")

    return render_template("profile.html", user=user, profile=profile, avatar_src=avatar_src)
