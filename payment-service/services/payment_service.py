from datetime import datetime
from typing import Optional
from db import db
from models import Payment, Contract, PaymentMethod, PaymentStatus
from config import Config
from utils.money_qr import bank_info

def create_payment_svc(data: dict) -> Payment:
    pay = Payment(
        order_id=int(data["order_id"]),
        buyer_id=int(data["buyer_id"]),
        seller_id=int(data["seller_id"]),
        amount=int(data["amount"]),
        method=PaymentMethod(data.get("method", PaymentMethod.E_WALLET.value)),
        provider=data.get("provider","ZaloPay"),
        status=PaymentStatus.PENDING,
    )
    db.session.add(pay); db.session.commit()
    return pay

def confirm_build_invoice_svc(pay: Payment, data: dict):
    c_invoice: Optional[Contract] = (
        Contract.query.filter(Contract.payment_id==pay.id, Contract.title.ilike("Hóa đơn/Contract%"))
        .order_by(Contract.id.desc()).first()
    )
    if not c_invoice:
        # validate form
        required = ["full_name","phone","email","address","province","district","ward"]
        miss = [k for k in required if not data.get(k)]
        if miss: raise ValueError("missing fields: " + ", ".join(miss))
        method_in = data.get("method")
        if method_in: pay.method = PaymentMethod(method_in)
        lines = [
            f"Họ tên: {data.get('full_name')}",
            f"Điện thoại: {data.get('phone')}",
            f"Email: {data.get('email')}",
            f"Địa chỉ: {data.get('address')}, {data.get('ward')}, {data.get('district')}, {data.get('province')}",
            f"Mã số thuế: {data.get('tax_code') or '(không)'}",
            f"Ghi chú: {data.get('note') or ''}",
            f"Hình thức thanh toán: {pay.method.value}",
            "",
            f"Số tiền: {pay.amount} VND",
            f"Số đơn hàng: {pay.order_id}",
            f"Thời gian: {datetime.utcnow().isoformat()}",
        ]
        c_invoice = Contract(payment_id=pay.id, title=f"Hóa đơn/Contract cho Payment #{pay.id}",
                             content="\n".join(lines), created_at=datetime.utcnow())
        db.session.add(c_invoice); db.session.commit()

    subtotal = int(pay.amount); vat = int(round(subtotal * Config.VAT_RATE)); grand = subtotal + vat
    bank = bank_info(grand, pay.id, pay.order_id)
    next_action = "show_qr" if pay.method in (PaymentMethod.BANKING, PaymentMethod.E_WALLET) else "show_cash_notice"
    payment_info = {
        "method": pay.method.value,
        "amount_vnd": f"{subtotal:,.0f} VND",
        "vat_vnd": f"{vat:,.0f} VND",
        "grand_vnd": f"{grand:,.0f} VND",
        **bank,
    }
    return c_invoice, payment_info, next_action
