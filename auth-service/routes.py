from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
import jwt, datetime, os

bp = Blueprint("auth", __name__, url_prefix="/auth")

# Đọc secret/algorithm thống nhất từ ENV (ưu tiên JWT_SECRET_KEY)
SECRET     = os.getenv("JWT_SECRET_KEY") or os.getenv("JWT_SECRET") or "supersecret-dev"
ALGORITHM  = os.getenv("JWT_ALGORITHM", "HS256")

# ===== Helpers =====
def _make_token(u: User) -> str:
    # PyJWT v2 yêu cầu 'sub' là STRING -> ép sang str để tránh InvalidSubjectError
    payload = {
        "sub": str(u.id),
        "username": u.username,
        "role": u.role,
        "approved": u.approved,
        "locked": u.locked,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=6),
    }
    token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)
    # PyJWT v1 trả bytes -> ép về str để chắc chắn
    if isinstance(token, bytes):
        token = token.decode()
    return token

def _decode_bearer_token(token: str):
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return payload, None
    except jwt.ExpiredSignatureError as e:
        print(f"[auth] decode error: ExpiredSignatureError: {e}")
        return None, ({"error": "expired"}, 401)
    except jwt.InvalidSignatureError as e:
        print(f"[auth] decode error: InvalidSignatureError: {e}")
        return None, ({"error": "bad_signature"}, 401)
    except jwt.DecodeError as e:
        print(f"[auth] decode error: DecodeError: {e}")
        return None, ({"error": "malformed"}, 401)
    except Exception as e:
        print(f"[auth] decode error: {type(e).__name__}: {e}")
        return None, ({"error": "invalid_token"}, 401)

def _require_admin():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, ({"error": "no_token"}, 401)
    token = auth.split(" ", 1)[1].strip()
    payload, err = _decode_bearer_token(token)
    if err:
        return None, err
    if payload.get("role") != "admin":
        return None, ({"error": "forbidden"}, 403)
    return payload, None

def _bearer_from_request():
    """Lấy token từ header Authorization: Bearer <token> (fallback x-access-token)"""
    auth = (request.headers.get("Authorization") or "").strip()
    parts = auth.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    # fallback cho một số client cũ
    return (request.headers.get("x-access-token") or "").strip()

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
    token = _bearer_from_request() \
            or (request.args.get("token") or "").strip() \
            or ((request.get_json(silent=True) or {}).get("token") or "").strip()

    if not token:
        return {"error": "no_token"}, 401

    payload, err = _decode_bearer_token(token)
    if err:
        return err

    # Chuẩn hoá response, ép sub về int nếu cần
    uid = payload.get("sub")
    try:
        uid = int(uid)
    except Exception:
        pass
    return jsonify({
        "id": uid,
        "username": payload.get("username"),
        "role": payload.get("role"),
        "approved": payload.get("approved"),
        "locked": payload.get("locked"),
    }), 200

# ===== Admin APIs (JWT role=admin) =====
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
        "is_admin": (u.role == "admin"),  # khớp với admin.html của gateway
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

# (Tùy chọn debug)
@bp.post("/debug/decode")
def debug_decode_no_verify():
    d = request.get_json(silent=True) or {}
    token = (d.get("token") or "").strip()
    if not token:
        return {"error": "no_token"}, 400
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return {"payload": payload}, 200
    except Exception as e:
        return {"error": f"malformed: {type(e).__name__}: {e}"}, 400
