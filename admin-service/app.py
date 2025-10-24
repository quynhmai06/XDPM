# admin-service/app.py
from flask import Flask, jsonify, request
import os, requests

app = Flask(__name__)

AUTH_URL = os.getenv("AUTH_URL", "http://auth_service:5001")  # DNS theo tên service trong compose
PORT = int(os.getenv("PORT", 5002))                           # khớp với cổng bạn đang dùng

@app.get("/health")
def health():
    return jsonify(ok=True, service="admin", auth_url=AUTH_URL)

@app.get("/")
def root():
    return jsonify(service="admin", status="ok", prefix="/admin")

@app.post("/admin/login")
def admin_login():
    data = request.get_json() or {}
    r = requests.post(f"{AUTH_URL}/auth/login", json={
        "email": data.get("email"),
        "password": data.get("password")
    }, timeout=5)
    if r.status_code != 200:
        return jsonify(error="auth_failed", detail=r.text), 401

    payload = r.json()
    # tuỳ payload của auth-service, ví dụ có field role
    if payload.get("role") != "admin":
        return jsonify(error="not_admin"), 403
    return jsonify(payload), 200

@app.get("/admin/verify")
def admin_verify():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return jsonify(error="missing_token"), 401
    r = requests.get(f"{AUTH_URL}/auth/verify",
                     headers={"Authorization": f"Bearer {token}"},
                     timeout=5)
    return (r.text, r.status_code, {"Content-Type": "application/json"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
