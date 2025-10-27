# admin-service/app.py
from flask import Flask, jsonify, request
import os, requests, json
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# ----------------- Config -----------------
AUTH_URL     = os.getenv("AUTH_URL", "http://auth_service:5001")
PAYMENT_URL  = os.getenv("PAYMENT_URL", "http://payment_service:5003")
PORT         = int(os.getenv("PORT", 5002))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///admin.db")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ----------------- Model ------------------
class PendingPaymentReview(db.Model):
    __tablename__ = "pending_payment_reviews"
    id         = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, nullable=False, index=True, unique=False)
    order_id   = db.Column(db.Integer, nullable=False)
    buyer_id   = db.Column(db.Integer, nullable=False)
    seller_id  = db.Column(db.Integer, nullable=False)
    amount     = db.Column(db.Integer, nullable=False)
    provider   = db.Column(db.String(50))
    method     = db.Column(db.String(20))
    status     = db.Column(db.String(20), default="pending", index=True)  # pending|approved|rejected
    note       = db.Column(db.Text)
    buyer_info = db.Column(db.Text)  # JSON stringified
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "payment_id": self.payment_id,
            "order_id": self.order_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "amount": self.amount,
            "provider": self.provider,
            "method": self.method,
            "status": self.status,
            "note": self.note or "",
            "buyer_info": json.loads(self.buyer_info or "{}"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

with app.app_context():
    db.create_all()

# ----------------- Helpers ----------------
def ok(data=None, code=200): return jsonify(data or {}), code
def err(msg, code=400):      return jsonify({"error": msg}), code

def _payment_post(path: str, **kwargs):
    """POST tới payment-service; trả (ok:boolean, resp_text_or_json, status)."""
    try:
        r = requests.post(f"{PAYMENT_URL}{path}", timeout=6, **kwargs)
        try:
            body = r.json()
        except Exception:
            body = r.text
        return r.ok, body, r.status_code
    except Exception as e:
        return False, str(e), 502

def _payment_get(path: str):
    try:
        r = requests.get(f"{PAYMENT_URL}{path}", timeout=6)
        try:
            body = r.json()
        except Exception:
            body = r.text
        return r.ok, body, r.status_code
    except Exception as e:
        return False, str(e), 502

# ----------------- Base/Health ------------
@app.get("/health")
def health():
    return ok({"ok": True, "service": "admin", "auth_url": AUTH_URL})

@app.get("/")
def root():
    return ok({"service": "admin", "status": "ok", "prefix": "/admin"})

# ----------------- Auth relay (tuỳ chọn) --
@app.post("/admin/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    # tuỳ auth-service: có thể dùng username/password hoặc email/password
    payload = {k: v for k, v in {
        "username": data.get("username"),
        "email": data.get("email"),
        "password": data.get("password"),
    }.items() if v}
    try:
        r = requests.post(f"{AUTH_URL}/auth/login", json=payload, timeout=6)
    except Exception as e:
        return err(f"auth_unreachable: {e}", 502)
    if r.status_code != 200:
        return err("auth_failed", 401)
    j = r.json()
    # nếu muốn bắt buộc role=admin:
    if j.get("role") not in (None, "admin"):  # nới lỏng nếu payload không có role
        return err("not_admin", 403)
    return ok(j)

@app.get("/admin/verify")
def admin_verify():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return err("missing_token", 401)
    try:
        r = requests.get(f"{AUTH_URL}/auth/verify",
                         headers={"Authorization": f"Bearer {token}"},
                         timeout=6)
        return (r.text, r.status_code, {"Content-Type": "application/json"})
    except Exception as e:
        return err(f"auth_unreachable: {e}", 502)

# ----------------- REVIEW API -------------
# 1) Payment-service gửi yêu cầu tạo review
@app.post("/admin/review/payment")
def create_review():
    data = request.get_json(silent=True) or {}
    required = ["payment_id", "order_id", "buyer_id", "seller_id", "amount"]
    miss = [k for k in required if data.get(k) in (None, "")]
    if miss:
        return err({"missing_fields": miss}, 400)

    # Idempotent: nếu đã có pending cho payment_id thì cập nhật thay vì tạo trùng
    r = PendingPaymentReview.query.filter_by(payment_id=int(data["payment_id"]), status="pending").first()
    if r:
        r.order_id  = int(data["order_id"])
        r.buyer_id  = int(data["buyer_id"])
        r.seller_id = int(data["seller_id"])
        r.amount    = int(data["amount"])
        r.provider  = data.get("provider") or r.provider
        r.method    = data.get("method") or r.method
        r.note      = data.get("note") or (r.note or "")
        r.buyer_info = json.dumps(data.get("buyer_info") or json.loads(r.buyer_info or "{}"), ensure_ascii=False)
        db.session.commit()
    else:
        r = PendingPaymentReview(
            payment_id = int(data["payment_id"]),
            order_id   = int(data["order_id"]),
            buyer_id   = int(data["buyer_id"]),
            seller_id  = int(data["seller_id"]),
            amount     = int(data["amount"]),
            provider   = data.get("provider") or "",
            method     = data.get("method") or "",
            status     = "pending",
            buyer_info = json.dumps(data.get("buyer_info") or {}, ensure_ascii=False),
            note       = data.get("note") or "",
        )
        db.session.add(r)
        db.session.commit()

    return ok({
        "message": "queued_for_review",
        "review_id": r.id,
        "review_url": f"/admin/review/payment/{r.id}"
    }, 201)

# 2) Lấy chi tiết 1 review
@app.get("/admin/review/payment/<int:rid>")
def get_review(rid: int):
    r = PendingPaymentReview.query.get(rid)
    if not r:
        return err("review_not_found", 404)
    return ok(r.to_dict())

# 3) Liệt kê (optional ?status=pending|approved|rejected)
@app.get("/admin/review/payment")
def list_reviews():
    st = request.args.get("status")
    q = PendingPaymentReview.query
    if st:
        q = q.filter_by(status=st)
    items = q.order_by(PendingPaymentReview.id.desc()).limit(200).all()
    return ok([i.to_dict() for i in items])

# 4) Approve → ưu tiên callback chuẩn; fallback simulate nếu callback không có
@app.post("/admin/review/payment/<int:rid>/approve")
def approve_review(rid: int):
    body = request.get_json(silent=True) or {}
    note = body.get("note", "")
    r = PendingPaymentReview.query.get(rid)
    if not r:          return err("review_not_found", 404)
    if r.status != "pending": return err("invalid_state", 409)

    # 4.1. Thử gọi callback chuẩn
    ok_cb, resp_cb, status_cb = _payment_post(f"/payment/review/{r.payment_id}/approve")
    if not ok_cb:
        # 4.2. Fallback qua simulate (giữ tương thích với bản payment-service cũ)
        ok_sim, resp_sim, status_sim = _payment_get(f"/payment/simulate/{r.payment_id}")
        if not ok_sim:
            return err({"payment_service_error": resp_cb, "fallback_error": resp_sim}, 502)

    r.status = "approved"
    r.note = note or r.note
    db.session.commit()
    return ok({"message": "approved", "payment_id": r.payment_id})

# 5) Reject → ưu tiên callback chuẩn; nếu không có callback thì chỉ đổi trạng thái tại admin
@app.post("/admin/review/payment/<int:rid>/reject")
def reject_review(rid: int):
    body = request.get_json(silent=True) or {}
    note = body.get("note", "")
    r = PendingPaymentReview.query.get(rid)
    if not r:          return err("review_not_found", 404)
    if r.status != "pending": return err("invalid_state", 409)

    ok_cb, resp_cb, status_cb = _payment_post(f"/payment/review/{r.payment_id}/reject")
    # nếu payment-service không hỗ trợ, vẫn coi như từ chối ở phía admin
    r.status = "rejected"
    r.note = note or r.note
    db.session.commit()
    return ok({"message": "rejected", "payment_id": r.payment_id, "payment_callback_ok": bool(ok_cb)})

# ----------------- Main -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
