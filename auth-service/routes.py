import os
import re
import jwt
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session, render_template, url_for, current_app, flash, redirect
from types import SimpleNamespace
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash   # ✅ thêm dòng này
from pathlib import Path
import uuid
from models import db, User, UserProfile


ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
AVATAR_DIR = "uploads/avatars"  # nằm trong static/

bp = Blueprint("auth", __name__, url_prefix="/auth")
SECRET = os.getenv("JWT_SECRET", "devsecret")  # nhớ đồng bộ với .env/docker


# -------------------- Helpers --------------------
def normalize_email(s: str | None) -> str | None:
    if not s:
        return None
    return s.strip().lower()


def normalize_phone(s: str | None) -> str | None:
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if digits.startswith("84"):
        digits = "0" + digits[2:]
    elif digits.startswith("084"):
        digits = "0" + digits[3:]
    return digits


def _make_token(u: User) -> str:
    payload = {
        "sub": u.id,
        "username": u.username,
        "role": u.role,
        "approved": u.approved,
        "locked": u.locked,
        "exp": datetime.utcnow() + timedelta(hours=6),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _require_admin():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, ({"error": "no_token"}, 401)
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    except Exception:
        return None, ({"error": "invalid_token"}, 401)
    if payload.get("role") != "admin":
        return None, ({"error": "forbidden"}, 403)
    return payload, None


def _require_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, ({"error": "no_token"}, 401)
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    except Exception:
        return None, ({"error": "invalid_token"}, 401)
    u = User.query.get(payload.get("sub"))
    if not u:
        return None, ({"error": "user_not_found"}, 404)
    if u.locked:
        return None, ({"error": "locked"}, 403)
    # Cho phép user thường cần approved; admin thì luôn pass
    if u.role != "admin" and not u.approved:
        return None, ({"error": "not_approved"}, 403)
    return u, None


# -------------------- Health --------------------
@bp.get("/")
def health():
    return {"service": "auth", "status": "ok", "prefix": "/auth"}


# -------------------- Auth: Register/Login --------------------
@bp.post("/register")
def register():
    d = request.get_json(force=True) if request.is_json else request.form
    username = (d.get("username") or "").strip()
    email = normalize_email(d.get("email"))
    phone = normalize_phone(d.get("phone"))
    password = d.get("password") or ""
    if not username or not email or not password:
        return {
            "error": "missing_fields",
            "hint": "username, email, password required",
        }, 400
    conds = [User.username == username, User.email == email]
    if phone:
        conds.append(User.phone == phone)
    existed = User.query.filter(or_(*conds)).first()
    if existed:
        if existed.username == username:
            return {"error": "username_exists"}, 409
        if existed.email == email:
            return {"error": "email_exists"}, 409
        if phone and existed.phone == phone:
            return {"error": "phone_exists"}, 409
    u = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        role="member",
        approved=False,  # member mới cần admin duyệt
        locked=False,
        phone=phone,
    )
    db.session.add(u)
    db.session.commit()
    return {"id": u.id, "username": u.username}, 201


@bp.route("/login", methods=["GET", "POST"])
def login():
    # nếu GET → hiển thị form login
    if request.method == "GET":
        return render_template("login.html")

    # nếu POST → xử lý form hoặc JSON
    data = request.get_json(force=True) if request.is_json else request.form
    identifier = (data.get("username") or data.get("identifier") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not identifier or not password:
        if request.is_json:
            return {"error": "missing_fields"}, 400
        flash("Vui lòng nhập đầy đủ thông tin!", "error")
        return redirect(url_for("auth.login"))

    # phân biệt username/email/số điện thoại
    by_email = "@" in identifier
    by_phone = identifier.isdigit()

    if by_email:
        u = User.query.filter_by(email=identifier.lower()).first()
    elif by_phone:
        u = User.query.filter_by(phone=normalize_phone(identifier)).first()
    else:
        u = User.query.filter_by(username=identifier).first()

    # kiểm tra tồn tại + mật khẩu
    if not u or not check_password_hash(u.password, password):
        if request.is_json:
            return {"error": "invalid_credentials"}, 401
        flash("Tên đăng nhập hoặc mật khẩu không đúng!", "error")
        return redirect(url_for("auth.login"))

    if u.locked:
        if request.is_json:
            return {"error": "locked"}, 403
        flash("Tài khoản của bạn đã bị khóa!", "error")
        return redirect(url_for("auth.login"))

    if u.role != "admin" and not u.approved:
        if request.is_json:
            return {"error": "not_approved"}, 403
        flash("Tài khoản chưa được admin duyệt!", "error")
        return redirect(url_for("auth.login"))

    # ---- Nếu thành công ----
    token = _make_token(u)

    # API mode
    if request.is_json:
        return {"access_token": token, "role": u.role}

    # Web mode
    session["user_id"] = u.id
    session["username"] = u.username
    session["role"] = u.role
    flash("Đăng nhập thành công!", "success")

    # điều hướng theo role
    if u.role == "admin":
        return redirect(url_for("auth.admin_list_users"))
    else:
        return redirect(url_for("auth.profile_page"))


@bp.get("/login")
def login_page():
    return render_template("login.html")


@bp.get("/me")
def me():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {"error": "no_token"}, 401
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], SECRET, algorithms=["HS256"])
    except Exception:
        return {"error": "invalid_token"}, 401
    return payload


# -------------------- Admin APIs --------------------
@bp.get("/admin/users")
def admin_list_users():
    _, err = _require_admin()
    if err:
        return err
    users = User.query.order_by(User.id.desc()).all()
    data = [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "is_admin": (u.role == "admin"),
            "approved": u.approved,
            "locked": u.locked,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]
    return {"data": data}


@bp.patch("/users/<int:uid>/status")
def update_status(uid: int):
    _, err = _require_admin()
    if err:
        return err
    d = request.get_json(force=True)
    status = (d.get("status") or "pending").lower()
    u = User.query.get_or_404(uid)
    if status == "approved":
        u.approved, u.locked = True, False
    elif status == "locked":
        u.approved, u.locked = False, True
    else:
        u.approved, u.locked = False, False
    db.session.commit()
    return {"ok": True, "status": status}


# -------------------- Profile APIs --------------------
@bp.get("/profile")
def get_profile():
    u, err = _require_user()
    if err:
        return err
    p = UserProfile.query.filter_by(user_id=u.id).first()
    if not p:
        p = UserProfile(user_id=u.id)
        db.session.add(p)
        db.session.commit()
    return {"user": u.to_dict_basic(), "profile": p.to_dict()}


@bp.put("/profile")
def update_profile():
    u, err = _require_user()
    if err:
        return err
    d = request.get_json(force=True)
    p = UserProfile.query.filter_by(user_id=u.id).first()
    if not p:
        p = UserProfile(user_id=u.id)
        db.session.add(p)
    # các field profile
    for field in ["full_name", "address", "vehicle_info", "battery_info", "avatar_url", "gender"]:
        if field in d:
            setattr(p, field, d[field])
    if "birthdate" in d:
        val = d.get("birthdate")
        if val:
            try:
                p.birthdate = datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                return {"error": "invalid_birthdate_format"}, 400
        else:
            p.birthdate = None
    # phone lưu ở bảng users
    if "phone" in d:
        u.phone = d.get("phone") or None
    db.session.commit()
    return {"ok": True, "profile": p.to_dict(), "user": u.to_dict_basic()}


@bp.put("/profile")
def _save_avatar(file_storage):
    if not file_storage or not file_storage.filename:
        return None, "no_file"
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        return None, "unsupported_type"
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = Path(current_app.static_folder) / AVATAR_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / filename
    file_storage.save(path)
    return filename, None


@bp.post("/profile")  # hỗ trợ form từ trình duyệt (multipart/form-data)
def update_profile_form():
    u, err = _require_user()
    if err:
        return err
    # Lấy/khởi tạo profile
    p = UserProfile.query.filter_by(user_id=u.id).first()
    if not p:
        p = UserProfile(user_id=u.id)
        db.session.add(p)
    # Field text từ form
    p.full_name = request.form.get("full_name") or p.full_name
    p.address = request.form.get("address") or p.address
    p.vehicle_info = request.form.get("vehicle_info") or p.vehicle_info
    p.battery_info = request.form.get("battery_info") or p.battery_info
    p.gender = request.form.get("gender") or p.gender
    birthdate = request.form.get("birthdate")
    if birthdate:
        try:
            from datetime import datetime
            p.birthdate = datetime.strptime(birthdate, "%Y-%m-%d").date()
        except ValueError:
            pass  # bỏ qua nếu sai format
    # Phone: có thể lưu ở bảng users (bạn đã dùng như vậy)
    phone = request.form.get("phone")
    if phone is not None:
        from re import sub
        digits = sub(r"\D", "", phone)
        if digits.startswith("84"):
            digits = "0" + digits[2:]
        if digits.startswith("084"):
            digits = "0" + digits[3:]
        u.phone = digits or None
    # File avatar
    file = request.files.get("avatar")
    if file and file.filename:
        filename, e = _save_avatar(file)
        if not e:
            p.avatar_url = filename  # chỉ lưu filename
    db.session.commit()
    # Trả JSON (gateway có thể redirect nếu muốn)
    return {
        "ok": True,
        "profile": p.to_dict(),
        "user": u.to_dict_basic(),
        "avatar_src": url_for("static", filename=f"{AVATAR_DIR}/{p.avatar_url}")
        if p.avatar_url
        else url_for("static", filename="img/avatar-placeholder.png"),
    }


# -------------------- Profile page (HTML) --------------------
@bp.get("/profile/view")  # KHÔNG trùng với API JSON
def profile_page():
    user_id = session.get("user_id")
    user = User.query.get(user_id)
    prof = UserProfile.query.filter_by(user_id=user_id).first()
    if prof is None:
        prof = SimpleNamespace(
            full_name="",
            phone="",
            address="",
            gender="",
            birthdate="",
            vehicle_info="",
            battery_info="",
            avatar_url="",
        )
    raw = getattr(prof, "avatar_url", "") or ""
    if raw.startswith(("http://", "https://", "/")):
        avatar_src = raw
    elif raw:
        avatar_src = url_for("static", filename=f"{AVATAR_DIR}/{raw}")
    else:
        avatar_src = url_for("static", filename="img/avatar-placeholder.png")
    return render_template("profile.html", user=user, profile=prof, avatar_src=avatar_src)
