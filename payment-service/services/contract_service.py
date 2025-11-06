from datetime import datetime
from db import db
from models import Contract, Payment
from utils.parsing import parse_kv_from_contract

def generate_vehicle_sale_contract(pay: Payment, buyer: dict) -> str:
    dmy = datetime.utcnow().strftime("%d/%m/%Y")
    amount_vnd = f"{pay.amount:,.0f} VND".replace(",", ",")
    lines = [
        "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "Độc lập - Tự do - Hạnh phúc", "",
        "HỢP ĐỒNG MUA BÁN XE", "",
        f"Hôm nay, ngày {dmy}, chúng tôi gồm có:", "",
        "Bên bán (Bên A)",
        "  - Doanh nghiệp: EV & Battery Platform",
        "  - Địa chỉ: 01 Sample Rd, Q1, TP.HCM",
        "  - Điện thoại: 028-000000     Email: support@evbattery.test", "",
        "Bên mua (Bên B)",
        f"  - Họ tên: {buyer.get('full_name')}",
        f"  - Địa chỉ: {buyer.get('address')}",
        f"  - Điện thoại: {buyer.get('phone')}     Email: {buyer.get('email')}", "",
        "Hai bên thống nhất ký kết ... (giữ nguyên điều khoản bản cũ) ...", "",
        f"Tham chiếu: Đơn hàng #{pay.order_id} • Mã giao dịch #{pay.id} • Ngày {dmy}",
    ]
    return "\n".join(lines)

def ensure_full_contract_for_invoice(pay: Payment, invoice_contract: Contract) -> Contract:
    buyer = parse_kv_from_contract(invoice_contract)
    c_full = Contract.query.filter(Contract.payment_id==pay.id,
                                   Contract.title.ilike("%HỢP ĐỒNG MUA BÁN XE%")).first()
    if not c_full:
        c_full = Contract(payment_id=pay.id, title="HỢP ĐỒNG MUA BÁN XE",
                          content=generate_vehicle_sale_contract(pay, buyer),
                          created_at=datetime.utcnow())
        db.session.add(c_full); db.session.commit()
    return c_full
