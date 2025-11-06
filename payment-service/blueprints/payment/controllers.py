# blueprints/payment/controllers.py
from datetime import datetime
from flask import request, render_template
from . import bp

from extensions import db
from models import Payment, Contract, PaymentMethod, PaymentStatus
from services.payment_service import create_payment_svc, confirm_build_invoice_svc
from services.contract_service import ensure_full_contract_for_invoice
from utils.responses import ok, err
from utils.parsing import parse_kv_from_contract
from config import Config


# ---------- Create ----------
@bp.post("/create")
def create_payment():
    data = request.get_json(silent=True) or {}
    required = ("order_id", "buyer_id", "seller_id", "amount")
    miss = [k for k in required if k not in data]
    if miss:
        return err("missing fields: " + ", ".join(miss), 400)
    try:
        pay = create_payment_svc(data)
        return ok(
            {
                "message": "Payment created",
                "payment_id": pay.id,
                "status": pay.status.value,
                "checkout_url": f"/payment/checkout/{pay.id}",
            },
            201,
        )
    except Exception as e:
        return err(f"db_error: {e}", 400)


# ---------- Get / List ----------
@bp.get("/<int:pid>")
def get_payment(pid: int):
    pay = Payment.query.get(pid)
    if not pay:
        return err("payment_not_found", 404)
    return ok(
        {
            "id": pay.id,
            "order_id": pay.order_id,
            "buyer_id": pay.buyer_id,
            "seller_id": pay.seller_id,
            "amount": pay.amount,
            "provider": pay.provider,
            "method": pay.method.value,
            "status": pay.status.value,
            "created_at": pay.created_at.isoformat(),
            "updated_at": pay.updated_at.isoformat() if pay.updated_at else None,
        }
    )


@bp.get("")
def list_payments():
    q = Payment.query.order_by(Payment.id.desc()).limit(100).all()
    return ok(
        [
            {
                "id": p.id,
                "order_id": p.order_id,
                "amount": p.amount,
                "status": p.status.value,
                "provider": p.provider,
                "created_at": p.created_at.isoformat(),
            }
            for p in q
        ]
    )


# ---------- Webhook demo ----------
@bp.post("/webhook/demo")
def webhook_demo():
    data = request.get_json(silent=True) or {}
    pid = data.get("payment_id")
    status = data.get("status", PaymentStatus.PAID.value)

    pay = Payment.query.get(pid)
    if not pay:
        return err("payment_not_found", 404)

    if status not in {s.value for s in PaymentStatus if s != PaymentStatus.REFUNDED}:
        return err("invalid_status", 400)

    pay.status = PaymentStatus(status)
    pay.updated_at = datetime.utcnow()
    db.session.commit()
    return ok({"message": "webhook_applied", "status": pay.status.value})


@bp.get("/simulate/<int:pid>")
def simulate_payment(pid: int):
    pay = Payment.query.get(pid)
    if not pay:
        return err("payment_not_found", 404)

    if pay.status == PaymentStatus.PAID:
        return ok({"message": "already_paid", "status": pay.status.value})

    pay.status = PaymentStatus.PAID
    pay.updated_at = datetime.utcnow()
    db.session.commit()
    return ok({"message": "Payment simulated", "status": pay.status.value})


# ---------- Cancel & Refund ----------
@bp.post("/cancel/<int:pid>")
def cancel_payment(pid: int):
    pay = Payment.query.get(pid)
    if not pay:
        return err("payment_not_found", 404)

    if pay.status == PaymentStatus.PAID:
        return err("cannot_cancel_paid", 409)

    pay.status = PaymentStatus.CANCELED
    pay.updated_at = datetime.utcnow()
    db.session.commit()
    return ok({"message": "canceled", "status": pay.status.value})


@bp.post("/refund/<int:pid>")
def refund_payment(pid: int):
    pay = Payment.query.get(pid)
    if not pay:
        return err("payment_not_found", 404)

    if pay.status != PaymentStatus.PAID:
        return err("only_paid_can_refund", 409)

    pay.status = PaymentStatus.REFUNDED
    pay.updated_at = datetime.utcnow()
    db.session.commit()
    return ok({"message": "refunded", "status": pay.status.value})


# ---------- Contract APIs ----------
@bp.post("/contract/create")
def create_contract():
    data = request.get_json(silent=True) or {}
    pid = data.get("payment_id")
    if not pid:
        return err("missing payment_id", 400)

    pay = Payment.query.get(pid)
    if not pay:
        return err("payment_not_found", 404)

    if pay.status != PaymentStatus.PAID:
        return err("payment_not_paid", 409)

    c = Contract(
        payment_id=pay.id,
        title=data.get("title", "Hợp đồng mua bán EV/Battery"),
        content=data.get("content", ""),
        created_at=datetime.utcnow(),
    )
    db.session.add(c)
    db.session.commit()
    return ok({"message": "Contract created", "contract_id": c.id}, 201)


@bp.post("/contract/sign")
def sign_contract():
    from utils.jwt_sign import sign_contract as _sign

    data = request.get_json(silent=True) or {}
    cid = data.get("contract_id")
    signer = data.get("signer_name")
    if not cid or not signer:
        return err("missing contract_id or signer_name", 400)

    c = Contract.query.get(cid)
    if not c:
        return err("contract_not_found", 404)

    payload = {
        "contract_id": c.id,
        "signer_name": signer,
        "payment_id": c.payment_id,
        "iat": int(datetime.utcnow().timestamp()),
    }
    token = _sign(payload)
    c.signer_name = signer
    c.signature_jwt = token
    c.signed_at = datetime.utcnow()
    db.session.commit()
    return ok({"message": "signed", "signature_jwt": token})


@bp.get("/contract/view/<int:cid>")
def view_contract(cid: int):
    c = Contract.query.get(cid)
    if not c:
        return err("contract_not_found", 404)

    return ok(
        {
            "id": c.id,
            "payment_id": c.payment_id,
            "title": c.title,
            "content": c.content,
            "signer_name": c.signer_name,
            "signature_jwt": c.signature_jwt,
            "signed_at": c.signed_at.isoformat() if c.signed_at else None,
            "created_at": c.created_at.isoformat(),
        }
    )


# ---------- UI pages ----------
@bp.get("/checkout/<int:pid>")
def checkout_page(pid: int):
    pay = Payment.query.get(pid)
    if not pay:
        return err("payment_not_found", 404)

    base_img_url = f"{Config.GATEWAY_URL}/static/images"
    img_map = {
        "zalo": f"{base_img_url}/zalopay.png",
        "momo": f"{base_img_url}/momo.png",
        "vinfast": f"{base_img_url}/v1.jpg",
        "tesla": f"{base_img_url}/v3.jpg",
        "oto": f"{base_img_url}/v5.jpg",
        "yamaha": f"{base_img_url}/ym1.jpg",
        "xe": f"{base_img_url}/y2.jpg",
    }
    provider_name = (pay.provider or "").lower()
    img_url = next((u for k, u in img_map.items() if k in provider_name), f"{base_img_url}/logo.png")
    status = pay.status.value
    status_cls = {
        "pending": "warning",
        "paid": "success",
        "canceled": "secondary",
        "refunded": "dark",
        "failed": "danger",
    }.get(status, "secondary")

    return render_template(
        "payment/checkout.html",
        pid=pay.id,
        order_id=pay.order_id,
        amount=pay.amount,
        method=pay.method.value,
        provider=pay.provider,
        status=status,
        status_cls=status_cls,
        img_url=img_url,
    )


@bp.get("/invoice/<int:cid>")
def invoice_page(cid: int):
    c = Contract.query.get(cid)
    if not c:
        return err("contract_not_found", 404)

    pay = Payment.query.get(c.payment_id)
    if not pay:
        return err("payment_not_found", 404)

    # đảm bảo có HỢP ĐỒNG đầy đủ để in
    c_full = ensure_full_contract_for_invoice(pay, c)

    # thông tin người mua rút từ hóa đơn (c)
    buyer = parse_kv_from_contract(c)

    subtotal = int(pay.amount)
    vat = int(round(subtotal * Config.VAT_RATE))
    grand = subtotal + vat
    from utils.money_qr import vnd

    status = pay.status.value
    status_cls = "success" if status == "paid" else ("warning" if status == "pending" else "secondary")

    return render_template(
        "payment/invoice.html",
        cid=cid, c=c, pay=pay, c_full=c_full, buyer=buyer,
        subtotal=subtotal, vat=vat, grand=grand, VAT_RATE=Config.VAT_RATE,
        vnd=vnd, status=status, status_cls=status_cls
    )


# ---------- Confirm + Update method ----------
@bp.post("/confirm/<int:pid>")
def confirm_and_pay(pid: int):
    pay = Payment.query.get(pid)
    if not pay:
        return err("payment_not_found", 404)

    data = request.get_json(silent=True) or {}
    try:
        invoice, payment_info, next_action = confirm_build_invoice_svc(pay, data)
        return ok(
            {
                "message": "invoice_ready",
                "status": pay.status.value,
                "invoice_url": f"/payment/invoice/{invoice.id}",
                "next_action": next_action,
                "payment_info": payment_info,
            }
        )
    except ValueError as ve:
        return err(str(ve), 400)


@bp.post("/update_method/<int:pid>")
def update_method(pid: int):
    pay = Payment.query.get(pid)
    if not pay:
        return err("payment_not_found", 404)

    data = request.get_json(silent=True) or {}
    method = data.get("method")
    if method not in [m.value for m in PaymentMethod]:
        return err("invalid_method", 400)

    pay.method = PaymentMethod(method)
    db.session.commit()
    return ok({"message": "method_updated", "method": pay.method.value})
