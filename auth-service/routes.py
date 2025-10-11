from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, OAuthAccount
import jwt, datetime, os
import re


bp = Blueprint("auth", __name__, url_prefix="/auth")
SECRET = os.getenv("JWT_SECRET", "devsecret")  

def _make_token(u: User) -> str:
    payload = {
        "sub": u.id,
        "username": u.username,
        "role": u.role,
        "approved": u.approved,
        "locked": u.locked,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=6),
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

def normalize_email(s: str|None) -> str|None:
    if not s: return None
    return s.strip().lower()

def normalize_phone(s: str|None) -> str|None:
    if not s: return None
    digits = re.sub(r"\D", "", s)  # giữ lại số
    if digits.startswith("84"):
        digits = "0" + digits[2:]
    elif digits.startswith("084"):
        digits = "0" + digits[3:]
    return digits

@bp.get("/")
def health():
    return {"service": "auth", "status": "ok"}

@bp.post("/register")
def register():
    d = request.get_json(force=True) if request.is_json else request.form
    username = (d.get("username") or "").strip()
    email    = normalize_email(d.get("email"))
    phone    = normalize_phone(d.get("phone"))  # NEW
    password = d.get("password") or ""

    if not username or not email or not password:
        return {"error": "missing_fields"}, 400

    # check trùng username, email, phone
    q = User.query.filter(
        (User.username == username) | (User.email == email) | ((User.phone == phone) if phone else False)
    ).first()
    if q:
        # trả về thông điệp phù hợp
        if q.username == username: return {"error": "username_exists"}, 409
        if q.email == email:       return {"error": "email_exists"}, 409
        if phone and q.phone == phone: return {"error": "phone_exists"}, 409

    u = User(username=username, email=email, password=generate_password_hash(password),
             role="member", approved=False, locked=False, phone=phone)
    db.session.add(u); db.session.commit()
    return {"id": u.id, "username": u.username}, 201

@bp.post("/login")
def login():
    d = request.get_json(force=True) if request.is_json else request.form
    identifier = (d.get("username") or d.get("identifier") or "").strip()
    password   = d.get("password") or ""

    if not identifier or not password:
        return {"error": "missing_fields"}, 400

    # đoán loại
    by_email = "@" in identifier
    by_phone = identifier.isdigit()

    email = normalize_email(identifier) if by_email else None
    phone = normalize_phone(identifier) if by_phone else None

    if by_email:
        u = User.query.filter_by(email=email).first()
    elif by_phone:
        u = User.query.filter_by(phone=phone).first()
    else:
        u = User.query.filter_by(username=identifier).first()

    if not u or not check_password_hash(u.password, password):
        return {"error": "invalid_credentials"}, 401
    if u.locked:
        return {"error": "locked"}, 403
    if not u.approved:
        return {"error": "not_approved"}, 403

    return {"access_token": _make_token(u)}

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

@bp.get("/admin/users")
def admin_list_users():
    _, err = _require_admin()
    if err:
        return err
    users = User.query.order_by(User.id.desc()).all()
    data = [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "is_admin": (u.role == "admin"), 
        "approved": u.approved,
        "locked": u.locked,
        "created_at": u.created_at.isoformat(),
    } for u in users]
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
