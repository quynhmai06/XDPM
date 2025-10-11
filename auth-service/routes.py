from flask import Blueprint, request
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
import jwt, datetime, os

bp = Blueprint("auth", __name__, url_prefix="/auth")
SECRET = os.getenv("JWT_SECRET", "devsecret")  # phải trùng với gateway

# ===== Helpers =====
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

# ===== Public =====
@bp.get("/")
def health():
    return {"service": "auth", "status": "ok"}

@bp.post("/register")
def register():
    d = request.get_json(force=True)
    username = (d.get("username") or "").strip()
    email    = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""

    if not username or not email or not password:
        return {"error": "missing_fields"}, 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return {"error": "exists"}, 409

    u = User(username=username, email=email,
             password=generate_password_hash(password),
             role="member", approved=False, locked=False)
    db.session.add(u)
    db.session.commit()
    return {"id": u.id, "username": u.username}, 201

@bp.post("/login")
def login():
    d = request.get_json(force=True)
    username = d.get("username") or ""
    password = d.get("password") or ""
    u = User.query.filter_by(username=username).first()
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
