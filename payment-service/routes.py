import os, jwt
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from db import db
from models import Payment, Contract

bp = Blueprint("payment", __name__, url_prefix="/payment")

JWT_SECRET = os.getenv("CONTRACT_SECRET", "contract-secret-demo")

@bp.get("/health")
def health():
    return {"status": "ok"}, 200

# --- Payments ---
@bp.post("/create")
def create_payment():
    d = request.get_json() or {}
    for k in ["order_id","buyer_id","seller_id","amount"]:
        if k not in d: return {"error": f"missing {k}"}, 400

    p = Payment(
        order_id=d["order_id"], buyer_id=d["buyer_id"],
        seller_id=d["seller_id"], amount=d["amount"],
        method=d.get("method","e-wallet"), provider=d.get("provider","DemoPay")
    )
    db.session.add(p); db.session.commit()
    # giả lập URL thanh toán
    checkout = f"/payment/simulate/{p.id}"
    return {"payment_id": p.id, "status": p.status, "checkout_url": checkout}, 201

@bp.get("/simulate/<int:pid>")
def simulate(pid):
    p = Payment.query.get(pid)
    if not p: return {"error":"not found"}, 404
    p.status = "paid"; db.session.commit()
    return {"payment_id": p.id, "status": p.status}, 200

# --- Contracts ---
@bp.post("/contract/create")
def contract_create():
    d = request.get_json() or {}
    for k in ["payment_id","title","content"]:
        if k not in d: return {"error": f"missing {k}"}, 400

    # yêu cầu payment phải tồn tại
    pay = Payment.query.get(d["payment_id"])
    if not pay: return {"error":"payment not found"}, 404

    c = Contract(payment_id=pay.id, title=d["title"], content=d["content"])
    db.session.add(c); db.session.commit()
    return {"contract_id": c.id}, 201

@bp.post("/contract/sign")
def contract_sign():
    d = request.get_json() or {}
    for k in ["contract_id","signer_name"]:
        if k not in d: return {"error": f"missing {k}"}, 400

    c = Contract.query.get(d["contract_id"])
    if not c: return {"error":"contract not found"}, 404

    payload = {
        "contract_id": c.id,
        "payment_id": c.payment_id,
        "signer_name": d["signer_name"],
        "signed_at": datetime.utcnow().isoformat()+"Z",
        "exp": datetime.utcnow() + timedelta(days=365)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    c.signer_name = d["signer_name"]
    c.signed_at = datetime.utcnow()
    c.signature_jwt = token
    db.session.commit()
    return {"contract_id": c.id, "signature_jwt": token}, 200

@bp.get("/contract/view/<int:cid>")
def contract_view(cid):
    c = Contract.query.get(cid)
    if not c: return {"error":"contract not found"}, 404
    return {
        "id": c.id,
        "payment_id": c.payment_id,
        "title": c.title,
        "content": c.content,
        "signed_at": c.signed_at.isoformat()+"Z" if c.signed_at else None,
        "signer_name": c.signer_name,
        "signature_jwt": c.signature_jwt,
    }, 200
