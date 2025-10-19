import os, jwt
from functools import wraps
from flask import request, jsonify

JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
JWT_ALGOS = [os.getenv("JWT_ALGOS", "HS256")]

def require_admin(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error":"missing_token"}), 401
        token = auth.split(" ",1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS)
        except Exception:
            return jsonify({"error":"invalid_token"}), 401
        if str(payload.get("role","")).lower() != "admin":
            return jsonify({"error":"forbidden"}), 403
        # đưa payload vào request context nếu cần:
        request.admin_payload = payload
        return fn(*args, **kwargs)
    return wrap
