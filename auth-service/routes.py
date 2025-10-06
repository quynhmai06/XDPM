from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
import jwt, datetime, os

bp = Blueprint("auth", __name__, url_prefix="/auth")
SECRET = os.getenv("JWT_SECRET", "devsecret")

def _token(u):
    payload = {
        "sub": u.id, "username": u.username, "role": u.role,
        "approved": u.approved, "locked": u.locked,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=6)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

@bp.get("/")
def health(): return {"service": "auth", "status": "ok"}

@bp.post("/register")
def register():
    d = request.get_json(force=True)
    if not d.get("username") or not d.get("email") or not d.get("password"):
        return {"error":"missing_fields"}, 400
    if User.query.filter((User.username==d["username"])|(User.email==d["email"])).first():
        return {"error":"exists"}, 409
    u = User(username=d["username"].strip(), email=d["email"].strip().lower(),
             password=generate_password_hash(d["password"]), approved=False)
    db.session.add(u); db.session.commit()
    return {"id": u.id, "username": u.username}, 201

@bp.post("/login")
def login():
    d = request.get_json(force=True)
    u = User.query.filter_by(username=d.get("username","")).first()
    if not u or not check_password_hash(u.password, d.get("password","")):
        return {"error":"invalid_credentials"}, 401
    return {"access_token": _token(u)}

@bp.get("/me")
def me():
    auth = request.headers.get("Authorization","")
    if not auth.startswith("Bearer "): return {"error":"no_token"}, 401
    try:
        payload = jwt.decode(auth.split(" ",1)[1], SECRET, algorithms=["HS256"])
        return payload
    except Exception:
        return {"error":"invalid_token"}, 401

@bp.patch("/users/<int:uid>/status")
def update_status(uid):
    # DEMO: dùng header X-Admin để kiểm soát; sau này verify JWT role=admin
    if request.headers.get("X-Admin") != "1":
        return {"error":"forbidden"}, 403
    d = request.get_json(force=True)
    status = (d.get("status") or "pending").lower()
    u = User.query.get_or_404(uid)
    if status == "approved": u.approved, u.locked = True, False
    elif status == "locked": u.approved, u.locked = False, True
    else: u.approved, u.locked = False, False
    db.session.commit()
    return {"ok": True, "status": status}
