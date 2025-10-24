# routes.py (REPLACE TOÀN BỘ NỘI DUNG)
from flask import Blueprint, request, jsonify
from datetime import datetime
from db import db
from models import Payment, Contract
import os, jwt

bp = Blueprint("payment", __name__)

JWT_SECRET = os.getenv("JWT_SECRET", "supersecret")
JWT_ALGO = "HS256"

# -----------------------------
# 1) Tạo thanh toán
# -----------------------------
@bp.post("/payment/create")
def create_payment():
    data = request.get_json(silent=True) or {}
    required = ["order_id", "buyer_id", "seller_id", "amount"]
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"error": f"missing fields: {', '.join(missing)}"}), 400

    try:
        pay = Payment(
            order_id=int(data["order_id"]),
            buyer_id=int(data["buyer_id"]),
            seller_id=int(data["seller_id"]),
            amount=int(data["amount"]),  # VND integer (khớp models)
            method=data.get("method", "e-wallet"),
            provider=data.get("provider", "DemoPay"),
            status="pending",
        )
        db.session.add(pay)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"db_error: {e}"}), 400

    return jsonify({
        "message": "Payment created",
        "payment_id": pay.id,
        "status": pay.status,
        "checkout_url": f"/payment/checkout/{pay.id}"
    }), 201

# -----------------------------
# 2) Lấy chi tiết / List
# -----------------------------
@bp.get("/payment/<int:pid>")
def get_payment(pid: int):
    pay = Payment.query.get(pid)
    if not pay:
        return jsonify({"error": "payment_not_found"}), 404
    return jsonify({
        "id": pay.id,
        "order_id": pay.order_id,
        "buyer_id": pay.buyer_id,
        "seller_id": pay.seller_id,
        "amount": pay.amount,
        "provider": pay.provider,
        "method": pay.method,
        "status": pay.status,
        "created_at": pay.created_at.isoformat() if pay.created_at else None,
        "updated_at": pay.updated_at.isoformat() if pay.updated_at else None
    })

@bp.get("/payment")
def list_payments():
    q = Payment.query.order_by(Payment.id.desc()).limit(100).all()
    return jsonify([
        {
            "id": p.id,
            "order_id": p.order_id,
            "amount": p.amount,
            "status": p.status,
            "provider": p.provider,
            "created_at": p.created_at.isoformat() if p.created_at else None
        } for p in q
    ])

# -----------------------------
# 3) (Demo) Webhook giả lập + simulate
# -----------------------------
@bp.post("/payment/webhook/demo")
def webhook_demo():
    """Webhook demo: body { "payment_id": 1, "status": "paid" | "failed" | "canceled" }"""
    data = request.get_json(silent=True) or {}
    pid = data.get("payment_id")
    status = data.get("status", "paid")
    pay = Payment.query.get(pid)
    if not pay:
        return jsonify({"error": "payment_not_found"}), 404

    if status not in ("paid", "failed", "canceled"):
        return jsonify({"error": "invalid_status"}), 400

    pay.status = status
    pay.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "webhook_applied", "status": pay.status})

@bp.get("/payment/simulate/<int:pid>")
def simulate_payment(pid: int):
    pay = Payment.query.get(pid)
    if not pay:
        return jsonify({"error": "payment_not_found"}), 404
    if pay.status == "paid":
        return jsonify({"message": "already_paid", "status": pay.status})
    pay.status = "paid"
    pay.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Payment simulated", "status": pay.status})

# -----------------------------
# 4) Cancel & Refund (mock)
# -----------------------------
@bp.post("/payment/cancel/<int:pid>")
def cancel_payment(pid: int):
    pay = Payment.query.get(pid)
    if not pay:
        return jsonify({"error": "payment_not_found"}), 404
    if pay.status == "paid":
        return jsonify({"error": "cannot_cancel_paid"}), 409
    pay.status = "canceled"
    pay.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "canceled", "status": pay.status})

@bp.post("/payment/refund/<int:pid>")
def refund_payment(pid: int):
    """Mock refund: chỉ đổi trạng thái để demo; thực tế gọi provider API."""
    pay = Payment.query.get(pid)
    if not pay:
        return jsonify({"error": "payment_not_found"}), 404
    if pay.status != "paid":
        return jsonify({"error": "only_paid_can_refund"}), 409
    pay.status = "refunded"
    pay.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "refunded", "status": pay.status})

# -----------------------------
# 5) Hợp đồng số (giữ nguyên + fix nhỏ)
# -----------------------------
@bp.post("/payment/contract/create")
def create_contract():
    data = request.get_json(silent=True) or {}
    pid = data.get("payment_id")
    if not pid:
        return jsonify({"error": "missing payment_id"}), 400
    pay = Payment.query.get(pid)
    if not pay:
        return jsonify({"error": "payment_not_found"}), 404
    if pay.status != "paid":
        return jsonify({"error": "payment_not_paid"}), 409

    c = Contract(
        payment_id=pay.id,
        title=data.get("title", "Hợp đồng mua bán EV/Battery"),
        content=data.get("content", ""),
        created_at=datetime.utcnow()
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({"message": "Contract created", "contract_id": c.id}), 201

@bp.post("/payment/contract/sign")
def sign_contract():
    data = request.get_json(silent=True) or {}
    cid = data.get("contract_id")
    signer = data.get("signer_name")
    if not cid or not signer:
        return jsonify({"error": "missing contract_id or signer_name"}), 400
    c = Contract.query.get(cid)
    if not c:
        return jsonify({"error": "contract_not_found"}), 404

    payload = {
        "contract_id": c.id,
        "signer_name": signer,
        "payment_id": c.payment_id,
        "iat": int(datetime.utcnow().timestamp())
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    c.signer_name = signer
    c.signature_jwt = token
    c.signed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "signed", "signature_jwt": token})

@bp.get("/payment/contract/view/<int:cid>")
def view_contract(cid: int):
    c = Contract.query.get(cid)
    if not c:
        return jsonify({"error": "contract_not_found"}), 404
    return jsonify({
        "id": c.id,
        "payment_id": c.payment_id,
        "title": c.title,
        "content": c.content,
        "signer_name": c.signer_name,
        "signature_jwt": c.signature_jwt,
        "signed_at": c.signed_at.isoformat() if c.signed_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None
    })
