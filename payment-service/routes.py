import os
import jwt
from datetime import datetime
from flask import Blueprint, jsonify, request, render_template_string
from db import db
from models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
    Contract,
    ContractType,
    ContractStatus,
    SignatureType,
)

bp = Blueprint("payment", __name__, url_prefix="/payment")

JWT_SECRET = os.getenv("JWT_SECRET", "supersecret")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")

BANK_NAME = os.getenv("BANK_NAME", "Vietcombank")
BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "0123456789")
BANK_OWNER = os.getenv("BANK_OWNER", "EV & Battery Platform")
VAT_RATE = float(os.getenv("VAT_RATE", "0.1"))


def _commit():
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _payment_json(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "order_id": payment.order_id,
        "buyer_id": payment.buyer_id,
        "seller_id": payment.seller_id,
        "amount": payment.amount,
        "method": payment.method.value,
        "provider": payment.provider,
        "status": payment.status.value,
        "created_at": payment.created_at.isoformat(),
        "updated_at": payment.updated_at.isoformat() if payment.updated_at else None,
        "contracts": [
            {
                "id": c.id,
                "type": c.contract_type.value,
                "title": c.title,
                "signed_at": c.signed_at.isoformat() if c.signed_at else None,
            }
            for c in payment.contracts
        ],
        "checkout_url": f"/payment/checkout/{payment.id}",
    }


def _ensure_sale_contract(payment: Payment, buyer_info: dict) -> Contract:
    existing = next(
        (c for c in payment.contracts if c.contract_type == ContractType.DIGITAL_SALE),
        None,
    )
    if existing:
        return existing

    now = datetime.utcnow().strftime("%d/%m/%Y")
    content = "\n".join(
        [
            "DIGITAL SALES CONTRACT",
            "",
            "Between:",
            "  Seller: EV & Battery Platform",
            "  Address: 01 Sample Road, District 1, Ho Chi Minh City",
            "",
            "And:",
            f"  Buyer: {buyer_info.get('full_name', '(Unknown)')}",
            f"  Phone: {buyer_info.get('phone', '(Unknown)')}",
            f"  Email: {buyer_info.get('email', '(Unknown)')}",
            f"  Address: {buyer_info.get('address', '(Unknown)')}",
            "",
            f"This contract relates to order #{payment.order_id} on {now}.",
            "The buyer agrees to purchase the product listed in the order.",
            "The seller agrees to deliver the product as described.",
            "Both parties agree to settle any dispute via negotiation." ,
        ]
    )
    contract = Contract(
        payment=payment,
        contract_type=ContractType.DIGITAL_SALE,
        title=f"Digital contract for payment #{payment.id}",
        content=content,
        created_at=datetime.utcnow(),
    )
    db.session.add(contract)
    _commit()
    return contract


def _invoice_contract(payment: Payment) -> Contract | None:
    return next(
        (c for c in payment.contracts if c.contract_type == ContractType.INVOICE),
        None,
    )


def _invoice_data(payload: dict, payment: Payment) -> dict:
    return {
        "full_name": payload.get("full_name", ""),
        "phone": payload.get("phone", ""),
        "email": payload.get("email", ""),
        "address": payload.get("address", ""),
        "tax_code": payload.get("tax_code", ""),
        "note": payload.get("note", ""),
        "method": payment.method.value,
    }


def _invoice_text(info: dict, payment: Payment) -> str:
    lines = [
        f"Invoice for payment #{payment.id}",
        f"Order id: {payment.order_id}",
        f"Buyer: {info['full_name']}",
        f"Phone: {info['phone']}",
        f"Email: {info['email']}",
        f"Address: {info['address']}",
        f"Tax code: {info['tax_code'] or 'N/A'}",
        f"Payment method: {info['method']}",
        f"Amount: {payment.amount} VND",
        f"Created at: {datetime.utcnow().isoformat()}",
    ]
    if info.get("note"):
        lines.append(f"Note: {info['note']}")
    return "\n".join(lines)


def _payment_response(payment: Payment, invoice: Contract) -> dict:
    subtotal = payment.amount
    vat = int(round(subtotal * VAT_RATE))
    total = subtotal + vat
    method = payment.method
    next_action = (
        "show_qr" if method in {PaymentMethod.E_WALLET, PaymentMethod.BANKING} else "show_cash_notice"
    )
    memo = f"PAY{payment.id}-ORD{payment.order_id}"
    return {
        "message": "invoice_ready",
        "status": payment.status.value,
        "invoice_id": invoice.id,
        "invoice_url": f"/payment/invoice/{invoice.id}",
        "next_action": next_action,
        "payment_info": {
            "amount_vnd": f"{subtotal:,.0f} VND",
            "vat_vnd": f"{vat:,.0f} VND",
            "grand_vnd": f"{total:,.0f} VND",
            "method": method.value,
            "bank_name": BANK_NAME,
            "bank_account": BANK_ACCOUNT,
            "bank_owner": BANK_OWNER,
            "memo": memo,
            "qr_text": f"{BANK_NAME}|{BANK_ACCOUNT}|{BANK_OWNER}|{memo}|{total}",
        },
    }


@bp.get("/health")
def health():
    return {"service": "payment", "status": "ok"}


@bp.post("/create")
def create_payment():
    data = request.get_json(force=True)
    print(f"DEBUG: Received payment data: {data}")  # Debug log
    required = ["order_id", "buyer_id", "seller_id", "amount"]
    missing = [k for k in required if k not in data]
    if missing:
        print(f"DEBUG: Missing fields: {missing}")  # Debug log
        return jsonify({"error": f"missing fields: {', '.join(missing)}"}), 400
    try:
        method = PaymentMethod(data.get("method", PaymentMethod.E_WALLET.value))
        print(f"DEBUG: Payment method: {method}")  # Debug log
    except ValueError as e:
        print(f"DEBUG: Invalid method error: {e}")  # Debug log
        return jsonify({"error": "invalid method"}), 400
    try:
        payment = Payment(
            order_id=str(data["order_id"]),  # Keep as string
            buyer_id=int(data["buyer_id"]),
            seller_id=int(data["seller_id"]),
            amount=float(data["amount"]),  # Use float for amount
            method=method,
            provider=data.get("provider", "Manual"),
        )
        print(f"DEBUG: Created payment object: {payment.id}")  # Debug log
        db.session.add(payment)
        _commit()
        print(f"DEBUG: Payment committed successfully: {payment.id}")  # Debug log
    except Exception as e:
        print(f"DEBUG: Error creating payment: {e}")  # Debug log
        import traceback
        traceback.print_exc()
        return jsonify({"error": "payment_creation_failed", "detail": str(e)}), 500
    return jsonify({
        "payment_id": payment.id,
        "id": payment.id,
        "order_id": payment.order_id,
        "status": payment.status.value,
        "amount": payment.amount,
        "checkout_url": f"/payment/checkout/{payment.id}"
    }), 201


@bp.get("")
def list_payments():
    query = Payment.query
    buyer_id = request.args.get("buyer_id", type=int)
    seller_id = request.args.get("seller_id", type=int)
    order_id = request.args.get("order_id", type=int)
    status = request.args.get("status")
    if buyer_id is not None:
        query = query.filter(Payment.buyer_id == buyer_id)
    if seller_id is not None:
        query = query.filter(Payment.seller_id == seller_id)
    if order_id is not None:
        query = query.filter(Payment.order_id == order_id)
    if status:
        try:
            query = query.filter(Payment.status == PaymentStatus(status))
        except ValueError:
            return jsonify({"error": "invalid status"}), 400
    items = query.order_by(Payment.created_at.desc()).limit(100).all()
    return jsonify({"items": [_payment_json(p) for p in items]})


@bp.get("/<int:payment_id>")
def get_payment(payment_id: int):
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"error": "not_found"}), 404
    return jsonify(_payment_json(payment))


@bp.post("/update_method/<int:payment_id>")
def update_method(payment_id: int):
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(force=True)
    method_value = data.get("method")
    try:
        payment.method = PaymentMethod(method_value)
    except Exception:
        return jsonify({"error": "invalid method"}), 400
    payment.updated_at = datetime.utcnow()
    _commit()
    return jsonify({"message": "updated", "method": payment.method.value})


@bp.post("/confirm/<int:payment_id>")
def confirm_payment(payment_id: int):
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"error": "not_found"}), 404
    payload = request.get_json(silent=True) or {}
    invoice = _invoice_contract(payment)
    if not invoice:
        required = ["full_name", "phone", "email", "address", "province", "district", "ward"]
        missing = [k for k in required if not payload.get(k)]
        if missing:
            return jsonify({"error": f"missing fields: {', '.join(missing)}"}), 400
        method_override = payload.get("method")
        if method_override:
            try:
                payment.method = PaymentMethod(method_override)
            except ValueError:
                return jsonify({"error": "invalid method"}), 400
        info = _invoice_data(payload, payment)
        info["province"] = payload.get("province")
        info["district"] = payload.get("district")
        info["ward"] = payload.get("ward")
        invoice = Contract(
            payment=payment,
            contract_type=ContractType.INVOICE,
            title=f"Invoice for payment #{payment.id}",
            content=_invoice_text(info, payment),
            extra_data=info,
            created_at=datetime.utcnow(),
        )
        db.session.add(invoice)
        _commit()
        _ensure_sale_contract(payment, info)
    return jsonify(_payment_response(payment, invoice))


@bp.post("/contract/create")
def create_contract():
    data = request.get_json(force=True)
    payment_id = data.get("payment_id")
    if not payment_id:
        return jsonify({"error": "missing payment_id"}), 400
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"error": "not_found"}), 404
    title = data.get("title", f"Digital contract for payment #{payment.id}")
    content = data.get("content", "Digital contract")
    contract = Contract(
        payment=payment,
        contract_type=ContractType.DIGITAL_SALE,
        title=title,
        content=content,
        created_at=datetime.utcnow(),
    )
    db.session.add(contract)
    _commit()
    return jsonify({"message": "created", "contract_id": contract.id}), 201


@bp.post("/contract/create-from-payment")
def create_contract_from_payment():
    """Create contract from payment with product details"""
    data = request.get_json(force=True)
    payment_id = data.get("payment_id")
    if not payment_id:
        return jsonify({"error": "missing payment_id"}), 400
    
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"error": "payment_not_found"}), 404
    
    # Check if contract already exists
    existing = Contract.query.filter_by(payment_id=payment_id).first()
    if existing:
        return jsonify({"message": "contract_exists", "contract_id": existing.id}), 200
    
    # Get product details from request
    product_info = data.get("product_info", {})
    buyer_info = data.get("buyer_info", {})
    seller_info = data.get("seller_info", {})
    cart_items = data.get("cart_items")  # optional, used by gateway callback to rebuild orders
    
    # Generate contract content
    title = f"HỢP ĐỒNG MUA BÁN PIN VÀ XE ĐIỆN - {payment.order_id}"
    content = f"""
HỢP ĐỒNG MUA BÁN PIN VÀ XE ĐIỆN QUA SỬ DỤNG

Mã hợp đồng: HD{payment.id}
Mã đơn hàng: {payment.order_id}

BÊN MUA (Bên A):
- Họ tên: {buyer_info.get('name', 'N/A')}
- Email: {buyer_info.get('email', 'N/A')}
- Số điện thoại: {buyer_info.get('phone', 'N/A')}

BÊN BÁN (Bên B):
- Họ tên: {seller_info.get('name', 'N/A')}
- Email: {seller_info.get('email', 'N/A')}
- Số điện thoại: {seller_info.get('phone', 'N/A')}

THÔNG TIN SẢN PHẨM:
{product_info.get('details', 'Chi tiết sản phẩm')}

GIÁ TRỊ HỢP ĐỒNG: {payment.amount:,.0f} VNĐ

ĐIỀU KHOẢN:
1. Bên A đồng ý mua sản phẩm với giá trị như trên
2. Bên B đảm bảo sản phẩm đúng mô tả và chất lượng
3. Thanh toán: Chuyển khoản ngân hàng qua VietQR
4. Giao hàng: Trong vòng 3-5 ngày làm việc
5. Bảo hành: Theo chính sách của nền tảng

Ngày lập: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}
"""
    
    # Build extra_data payload including cart items if provided
    extra_payload = {
        'product_info': product_info,
        'buyer_info': buyer_info,
        'seller_info': seller_info
    }
    if cart_items:
        extra_payload['cart_items'] = cart_items

    contract = Contract(
        payment=payment,
        contract_type=ContractType.DIGITAL_SALE,
        contract_status=ContractStatus.PENDING_SIGNATURE,
        title=title,
        content=content,
        extra_data=extra_payload,
        created_at=datetime.utcnow(),
    )
    db.session.add(contract)
    _commit()
    
    return jsonify({
        "message": "contract_created",
        "contract_id": contract.id,
        "contract_code": f"HD{contract.id}",
        "status": contract.contract_status.value
    }), 201


@bp.post("/contract/sign")
def sign_contract():
    """Legacy sign contract endpoint"""
    data = request.get_json(force=True)
    contract_id = data.get("contract_id")
    signer_name = data.get("signer_name")
    if not contract_id or not signer_name:
        return jsonify({"error": "missing arguments"}), 400
    contract = Contract.query.get(contract_id)
    if not contract:
        return jsonify({"error": "not_found"}), 404
    payload = {
        "contract_id": contract.id,
        "payment_id": contract.payment_id,
        "signer": signer_name,
        "iat": int(datetime.utcnow().timestamp()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    contract.signer_name = signer_name
    contract.signature_jwt = token
    contract.signed_at = datetime.utcnow()
    _commit()
    return jsonify({"message": "signed", "signature_jwt": token})


@bp.post("/contract/sign/<int:contract_id>")
def sign_contract_v2(contract_id: int):
    """Sign contract with buyer/seller signature (text or image)"""
    data = request.get_json(force=True)
    
    contract = Contract.query.get(contract_id)
    if not contract:
        return jsonify({"error": "contract_not_found"}), 404
    
    signer_role = data.get("signer_role")  # 'buyer' or 'seller'
    signature_type = data.get("signature_type")  # 'text' or 'image'
    signature_data = data.get("signature_data")  # Full name or base64 image
    
    if not all([signer_role, signature_type, signature_data]):
        return jsonify({"error": "missing_signature_data"}), 400
    
    if signer_role not in ['buyer', 'seller']:
        return jsonify({"error": "invalid_signer_role"}), 400
    
    if signature_type not in ['text', 'image']:
        return jsonify({"error": "invalid_signature_type"}), 400
    
    now = datetime.utcnow()
    
    # Update signature based on role
    if signer_role == 'buyer':
        contract.buyer_signature_type = SignatureType.TEXT if signature_type == 'text' else SignatureType.IMAGE
        contract.buyer_signature_data = signature_data
        contract.buyer_signed_at = now
    else:  # seller
        contract.seller_signature_type = SignatureType.TEXT if signature_type == 'text' else SignatureType.IMAGE
        contract.seller_signature_data = signature_data
        contract.seller_signed_at = now
    
    # Check if both parties have signed
    if contract.buyer_signed_at and contract.seller_signed_at:
        contract.contract_status = ContractStatus.SIGNED
        contract.signed_at = now
    
    _commit()
    
    return jsonify({
        "message": "signature_recorded",
        "contract_id": contract.id,
        "signer_role": signer_role,
        "contract_status": contract.contract_status.value,
        "buyer_signed": contract.buyer_signed_at is not None,
        "seller_signed": contract.seller_signed_at is not None
    }), 200


@bp.get("/contract/view/<int:contract_id>")
def view_contract(contract_id: int):
    contract = Contract.query.get(contract_id)
    if not contract:
        return jsonify({"error": "not_found"}), 404
    
    payment = contract.payment
    
    return jsonify(
        {
            "id": contract.id,
            "payment_id": contract.payment_id,
            "type": contract.contract_type.value,
            "status": contract.contract_status.value if hasattr(contract, 'contract_status') else 'draft',
            "title": contract.title,
            "content": contract.content,
            "signer_name": contract.signer_name,
            "signed_at": contract.signed_at.isoformat() if contract.signed_at else None,
            "signature_jwt": contract.signature_jwt,
            "created_at": contract.created_at.isoformat(),
            "contract_code": f"HD{contract.id}",
            # New signature fields
            "buyer_signature_type": contract.buyer_signature_type.value if contract.buyer_signature_type else None,
            "buyer_signature_data": contract.buyer_signature_data,
            "buyer_signed_at": contract.buyer_signed_at.isoformat() if contract.buyer_signed_at else None,
            "seller_signature_type": contract.seller_signature_type.value if contract.seller_signature_type else None,
            "seller_signature_data": contract.seller_signature_data,
            "seller_signed_at": contract.seller_signed_at.isoformat() if contract.seller_signed_at else None,
            # Payment info
            "payment": {
                "order_id": payment.order_id,
                "amount": float(payment.amount),
                "buyer_id": payment.buyer_id,
                "seller_id": payment.seller_id,
                "method": payment.method.value,
                "status": payment.status.value
            } if payment else None,
            "extra_data": contract.extra_data,
            "extra_data": contract.extra_data,
        }
    )


@bp.get("/contract/preview/<int:contract_id>")
def preview_contract(contract_id: int):
    contract = Contract.query.get(contract_id)
    if not contract:
        return "Not found", 404
    template = """
<!doctype html>
<title>Contract {{ contract.id }}</title>
<h1>{{ contract.title }}</h1>
<pre>{{ contract.content }}</pre>
{% if contract.signer_name %}
<p>Signed by {{ contract.signer_name }} at {{ contract.signed_at }}</p>
{% endif %}
"""
    return render_template_string(template, contract=contract)


@bp.get("/invoice/<int:contract_id>")
def invoice_page(contract_id: int):
    contract = Contract.query.get(contract_id)
    if not contract or contract.contract_type != ContractType.INVOICE:
        return "Not found", 404
    payment = contract.payment
    info = contract.extra_data or {}
    template = """
<!doctype html>
<title>Invoice {{ contract.id }}</title>
<h1>Invoice for payment {{ payment.id }}</h1>
<ul>
  <li>Order: {{ payment.order_id }}</li>
  <li>Buyer: {{ info.get('full_name', '') }}</li>
  <li>Amount: {{ payment.amount }} VND</li>
  <li>Method: {{ payment.method.value }}</li>
</ul>
<p><a href="/payment/contract/preview/{{ contract.id }}">Download raw invoice text</a></p>
"""
    return render_template_string(template, contract=contract, payment=payment, info=info)


@bp.get("/checkout/<int:payment_id>")
def checkout_page(payment_id: int):
    payment = Payment.query.get(payment_id)
    if not payment:
        return "Not found", 404
    invoice = _invoice_contract(payment)
    template = """
<!doctype html>
<title>Checkout {{ payment.id }}</title>
<h1>Checkout for order {{ payment.order_id }}</h1>
<p>Amount: {{ payment.amount }} VND</p>
<p>Status: {{ payment.status.value }}</p>
{% if invoice %}
<p>Invoice ready. <a href="/payment/invoice/{{ invoice.id }}">View invoice</a></p>
{% else %}
<form id="invoiceForm">
  <p>Provide invoice information to continue.</p>
  <input name="full_name" placeholder="Full name" required>
  <input name="phone" placeholder="Phone" required>
  <input name="email" placeholder="Email" required>
  <input name="address" placeholder="Address" required>
  <input name="province" placeholder="Province" required>
  <input name="district" placeholder="District" required>
  <input name="ward" placeholder="Ward" required>
  <button type="submit">Create invoice</button>
</form>
<div id="msg"></div>
<script>
  document.getElementById('invoiceForm').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const formData = new FormData(ev.target);
    const payload = Object.fromEntries(formData.entries());
    const res = await fetch('/payment/confirm/{{ payment.id }}', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if(res.ok){
      window.location.href = data.invoice_url;
    }else{
      document.getElementById('msg').textContent = data.error || 'Could not create invoice';
    }
  });
</script>
{% endif %}
"""
    return render_template_string(template, payment=payment, invoice=invoice)


@bp.post("/simulate/<int:payment_id>")
def simulate_paid(payment_id: int):
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"error": "not_found"}), 404
    payment.status = PaymentStatus.PAID
    payment.updated_at = datetime.utcnow()
    _commit()
    return jsonify({"message": "updated", "status": payment.status.value})


@bp.get("/status/<int:payment_id>")
def payment_status(payment_id: int):
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"error": "not_found"}), 404

    return jsonify({
        "payment_id": payment.id,
        "order_id": payment.order_id,
        "status": payment.status.value,
        "provider": payment.provider,
        "amount": payment.amount
    })
