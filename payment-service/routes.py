# routes.py
from flask import Blueprint, request, jsonify, render_template_string
from datetime import datetime
from db import db
from models import Payment, Contract, PaymentMethod, PaymentStatus
import os, jwt

bp = Blueprint("payment", __name__)

JWT_SECRET = os.getenv("JWT_SECRET", "supersecret")
JWT_ALGO   = "HS256"

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")

# ---------- helpers ----------
def ok(data=None, code=200):  return (jsonify(data or {}), code)
def err(msg, code=400):       return (jsonify({"error": msg}), code)

def commit_or_rollback():
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e

# -------- helpers ----------
def _parse_kv_from_contract(c: Contract):
    kv = {}
    for line in (c.content or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip().lower()] = v.strip()

    def pick(*keys, default=""):
        for k in keys:
            v = kv.get(k.lower())
            if v: return v
        return default

    return {
        "full_name": pick("Họ tên", "ho ten", default="(Không rõ)"),
        "phone":     pick("Điện thoại", "dien thoai"),
        "email":     pick("Email"),
        "address":   pick("Địa chỉ", "dia chi"),
        "tax_code":  pick("Mã số thuế", "ma so thue", default="(không)"),
        "note":      pick("Ghi chú", "ghi chu"),
    }

def _generate_vehicle_sale_contract(pay: Payment, buyer: dict) -> str:
    today = datetime.utcnow()
    dmy = today.strftime("%d/%m/%Y")
    amount_vnd = f"{pay.amount:,.0f} VND".replace(",", ",")

    lines = [
        "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "Độc lập - Tự do - Hạnh phúc",
        "",
        "HỢP ĐỒNG MUA BÁN XE",
        "",
        f"Hôm nay, ngày {dmy}, chúng tôi gồm có:",
        "",
        "Bên bán (Bên A)",
        "  - Doanh nghiệp: EV & Battery Platform",
        "  - Địa chỉ: 01 Sample Rd, Q1, TP.HCM",
        "  - Điện thoại: 028-000000     Email: support@evbattery.test",
        "",
        "Bên mua (Bên B)",
        f"  - Họ tên: {buyer.get('full_name')}",
        f"  - Địa chỉ: {buyer.get('address')}",
        f"  - Điện thoại: {buyer.get('phone')}     Email: {buyer.get('email')}",
        "",
        "Hai bên thống nhất ký kết Hợp đồng mua bán xe với các điều khoản sau:",
        "",
        "ĐIỀU 1. Hàng hóa giao dịch",
        "  1. Tên hàng hóa: Xe/Phương tiện (EV/Battery).",
        "  2. Thông số cơ bản (bổ sung khi bàn giao): Biển số/Seri – Nhãn hiệu – Dòng xe – Màu sơn – Số khung – Số máy.",
        "  3. Tình trạng: mới/đã qua sử dụng (tùy model) kèm phụ kiện tiêu chuẩn.",
        "",
        "ĐIỀU 2. Giá bán và thanh toán",
        f"  1. Giá bán: {amount_vnd} (đã/chưa gồm VAT tùy hóa đơn).",
        f"  2. Hình thức thanh toán: {pay.method.value}.",
        "  3. Thời điểm thanh toán: theo thỏa thuận/đặt cọc/1 lần khi nhận xe.",
        "",
        "ĐIỀU 3. Bàn giao & sở hữu",
        "  1. Bên A bàn giao xe và giấy tờ tại địa điểm thỏa thuận.",
        "  2. Quyền sở hữu chuyển cho Bên B sau khi hoàn tất thanh toán & bàn giao.",
        "",
        "ĐIỀU 4. Bảo hành & hỗ trợ",
        "  1. Theo chính sách nhà sản xuất/EV & Battery.",
        "",
        "ĐIỀU 5. Thuế, phí & công chứng",
        "  1. Thuế/phí trước bạ, đăng ký, công chứng… theo thỏa thuận.",
        "",
        "ĐIỀU 6. Hủy/hoàn tiền",
        "  1. Nếu hủy do khách quan, thương lượng hoàn tiền/đổi lịch.",
        "  2. Nếu Bên B đơn phương hủy sau đặt cọc, khoản cọc có thể không được hoàn.",
        "",
        "ĐIỀU 7. Cam kết chung",
        "  - Thông tin đúng sự thật; hai bên tự nguyện giao kết và thực hiện đúng thỏa thuận.",
        "",
        "ĐIỀU 8. Giải quyết tranh chấp",
        "  - Thương lượng; nếu không đạt, yêu cầu Tòa án có thẩm quyền giải quyết.",
        "",
        "ĐIỀU 9. Hiệu lực",
        "  - Hợp đồng có hiệu lực kể từ ngày ký; lập thành 02 bản, mỗi bên giữ 01 bản.",
        "",
        "ĐẠI DIỆN CÁC BÊN KÝ XÁC NHẬN",
        "BÊN A (Bán)                                BÊN B (Mua)",
        "(Ký & ghi rõ họ tên)                       (Ký & ghi rõ họ tên)",
        "",
        f"Tham chiếu: Đơn hàng #{pay.order_id} • Mã giao dịch #{pay.id} • Ngày {dmy}",
    ]
    return "\n".join(lines)

# ---------- 1) Create payment ----------
@bp.post("/payment/create")
def create_payment():
    data = request.get_json(silent=True) or {}
    required = ("order_id", "buyer_id", "seller_id", "amount")
    missing = [k for k in required if k not in data]
    if missing: return err(f"missing fields: {', '.join(missing)}", 400)

    try:
        pay = Payment(
            order_id = int(data["order_id"]),
            buyer_id = int(data["buyer_id"]),
            seller_id= int(data["seller_id"]),
            amount   = int(data["amount"]),
            method   = PaymentMethod(data.get("method", PaymentMethod.E_WALLET.value)),
            provider = data.get("provider", os.getenv("DEFAULT_PROVIDER", "ZaloPay")),
            status   = PaymentStatus.PENDING,
        )
        db.session.add(pay)
        commit_or_rollback()
    except Exception as e:
        return err(f"db_error: {e}", 400)

    return ok({
        "message": "Payment created",
        "payment_id": pay.id,
        "status": pay.status.value,
        "checkout_url": f"/payment/checkout/{pay.id}"
    }, 201)

# ---------- 2) Get / List ----------
@bp.get("/payment/<int:pid>")
def get_payment(pid: int):
    pay = Payment.query.get(pid)
    if not pay: return err("payment_not_found", 404)
    return ok({
        "id": pay.id,
        "order_id": pay.order_id,
        "buyer_id": pay.buyer_id,
        "seller_id": pay.seller_id,
        "amount": pay.amount,
        "provider": pay.provider,
        "method": pay.method.value,
        "status": pay.status.value,
        "created_at": pay.created_at.isoformat(),
        "updated_at": pay.updated_at.isoformat() if pay.updated_at else None
    })

@bp.get("/payment")
def list_payments():
    q = Payment.query.order_by(Payment.id.desc()).limit(100).all()
    return ok([
        {
            "id": p.id,
            "order_id": p.order_id,
            "amount": p.amount,
            "status": p.status.value,
            "provider": p.provider,
            "created_at": p.created_at.isoformat()
        } for p in q
    ])

# ---------- 3) Webhook demo ----------
@bp.post("/payment/webhook/demo")
def webhook_demo():
    data = request.get_json(silent=True) or {}
    pid = data.get("payment_id")
    status = data.get("status", PaymentStatus.PAID.value)
    pay = Payment.query.get(pid)
    if not pay: return err("payment_not_found", 404)
    if status not in {s.value for s in PaymentStatus if s != PaymentStatus.REFUNDED}:
        return err("invalid_status", 400)

    pay.status = PaymentStatus(status)
    pay.updated_at = datetime.utcnow()
    commit_or_rollback()
    return ok({"message": "webhook_applied", "status": pay.status.value})

@bp.get("/payment/simulate/<int:pid>")
def simulate_payment(pid: int):
    pay = Payment.query.get(pid)
    if not pay: return err("payment_not_found", 404)
    if pay.status == PaymentStatus.PAID:
        return ok({"message": "already_paid", "status": pay.status.value})
    pay.status = PaymentStatus.PAID
    pay.updated_at = datetime.utcnow()
    commit_or_rollback()
    return ok({"message": "Payment simulated", "status": pay.status.value})

# ---------- 4) Cancel & Refund ----------
@bp.post("/payment/cancel/<int:pid>")
def cancel_payment(pid: int):
    pay = Payment.query.get(pid)
    if not pay: return err("payment_not_found", 404)
    if pay.status == PaymentStatus.PAID:
        return err("cannot_cancel_paid", 409)
    pay.status = PaymentStatus.CANCELED
    pay.updated_at = datetime.utcnow()
    commit_or_rollback()
    return ok({"message": "canceled", "status": pay.status.value})

@bp.post("/payment/refund/<int:pid>")
def refund_payment(pid: int):
    pay = Payment.query.get(pid)
    if not pay: return err("payment_not_found", 404)
    if pay.status != PaymentStatus.PAID:
        return err("only_paid_can_refund", 409)
    pay.status = PaymentStatus.REFUNDED
    pay.updated_at = datetime.utcnow()
    commit_or_rollback()
    return ok({"message": "refunded", "status": pay.status.value})

# ---------- 5) Contract APIs ----------
@bp.post("/payment/contract/create")
def create_contract():
    data = request.get_json(silent=True) or {}
    pid = data.get("payment_id")
    if not pid: return err("missing payment_id", 400)
    pay = Payment.query.get(pid)
    if not pay: return err("payment_not_found", 404)
    if pay.status != PaymentStatus.PAID:
        return err("payment_not_paid", 409)

    c = Contract(
        payment_id=pay.id,
        title=data.get("title", "Hợp đồng mua bán EV/Battery"),
        content=data.get("content", ""),
        created_at=datetime.utcnow()
    )
    db.session.add(c)
    commit_or_rollback()
    return ok({"message": "Contract created", "contract_id": c.id}, 201)

@bp.post("/payment/contract/sign")
def sign_contract():
    data = request.get_json(silent=True) or {}
    cid = data.get("contract_id")
    signer = data.get("signer_name")
    if not cid or not signer:
        return err("missing contract_id or signer_name", 400)
    c = Contract.query.get(cid)
    if not c: return err("contract_not_found", 404)

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
    commit_or_rollback()
    return ok({"message": "signed", "signature_jwt": token})

@bp.get("/payment/contract/view/<int:cid>")
def view_contract(cid: int):
    c = Contract.query.get(cid)
    if not c: return err("contract_not_found", 404)
    return ok({
        "id": c.id,
        "payment_id": c.payment_id,
        "title": c.title,
        "content": c.content,
        "signer_name": c.signer_name,
        "signature_jwt": c.signature_jwt,
        "signed_at": c.signed_at.isoformat() if c.signed_at else None,
        "created_at": c.created_at.isoformat()
    })

# ---------- 5b) Contract preview ----------
@bp.get("/payment/contract/preview/<int:cid>")
def preview_contract(cid: int):
    c = Contract.query.get(cid)
    if not c: return err("contract_not_found", 404)
    pay = Payment.query.get(c.payment_id)
    if not pay: return err("payment_not_found", 404)

    html = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <title>Hợp đồng #{{ c.id }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    *{font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
    body{background:#f5f7fb}
    .sheet{max-width:900px;margin:28px auto;background:#fff;border-radius:16px;box-shadow:0 12px 28px rgba(0,0,0,.08);padding:32px}
    .head{text-align:center;margin-bottom:8px}
    .head .sup{font-weight:600}
    .head .title{font-weight:800;font-size:22px;letter-spacing:.3px;margin-top:8px}
    .meta{color:#64748b;font-size:14px;text-align:center;margin-bottom:18px}
    .content{white-space:pre-wrap;line-height:1.7;font-size:15.5px}
    .sign{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:28px}
    .sign .box{border:1px dashed #cbd5e1;border-radius:10px;padding:18px;text-align:center}
    .sign .box b{display:block;margin-bottom:8px}
    .actions{display:flex;gap:8px;justify-content:flex-end;margin-top:14px}
    @media print{ .actions{display:none} body{background:#fff} .sheet{box-shadow:none;border-radius:0} }
  </style>
</head>
<body>
  <div class="sheet">
    <div class="actions">
      <button class="btn btn-primary btn-sm" onclick="window.print()">In / Lưu PDF</button>
    </div>

    <div class="head">
      <div class="sup">CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</div>
      <div class="sup">Độc lập - Tự do - Hạnh phúc</div>
      <div class="title">HỢP ĐỒNG MUA BÁN XE</div>
    </div>
    <div class="meta">Mã hợp đồng: {{ c.id }} • Mã giao dịch: {{ pay.id }} • Số đơn hàng: {{ pay.order_id }}</div>

    <div class="content">{{ c.content|e }}</div>

    <div class="sign">
      <div class="box">
        <b>BÊN A (Bán)</b>
        <div>(Ký, ghi rõ họ tên)</div>
      </div>
      <div class="box">
        <b>BÊN B (Mua)</b>
        <div>(Ký, ghi rõ họ tên)</div>
      </div>
    </div>
  </div>
</body>
</html>
    """
    return render_template_string(html, c=c, pay=pay)

# ---------- 6) Checkout (tạo hóa đơn rồi vào trang hóa đơn) ----------
@bp.get("/payment/checkout/<int:pid>")
def checkout_page(pid: int):
    pay = Payment.query.get(pid)
    if not pay: return err("payment_not_found", 404)

    base_img_url = f"{GATEWAY_URL}/static/images"
    img_map = {
        "zalo":    f"{base_img_url}/zalopay.png",
        "momo":    f"{base_img_url}/momo.png",
        "vinfast": f"{base_img_url}/v1.jpg",
        "tesla":   f"{base_img_url}/v3.jpg",
        "oto":     f"{base_img_url}/v5.jpg",
        "yamaha":  f"{base_img_url}/ym1.jpg",
        "xe":      f"{base_img_url}/y2.jpg",
    }
    provider_name = (pay.provider or "").lower()
    img_url = next((url for key, url in img_map.items() if key in provider_name), f"{base_img_url}/logo.png")

    status = pay.status.value
    status_cls = {
        "pending":  "warning",
        "paid":     "success",
        "canceled": "secondary",
        "refunded": "dark",
        "failed":   "danger",
    }.get(status, "secondary")

    html = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <title>Thanh toán đơn hàng #{{ pid }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body{background:linear-gradient(145deg,#f3f6ff,#eaefff);min-height:100vh}
    .wrap{max-width:1100px;margin:40px auto}
    .hero{background:#0d47a1;color:#fff;border-radius:16px;padding:18px 24px;box-shadow:0 8px 20px rgba(13,71,161,.18)}
    .cardx{background:#fff;border-radius:16px;box-shadow:0 10px 24px rgba(0,0,0,.08);overflow:hidden}
    .thumb{min-height:260px;background:#f8fafc;display:flex;align-items:center;justify-content:center}
    .thumb img{max-height:260px;width:100%;object-fit:cover}
    .info{padding:22px}
    .info .kv{display:flex;justify-content:space-between;gap:8px;padding:10px 0;border-bottom:1px dashed #e5e7eb}
    .actions{padding:18px;border-top:1px solid #eef2f7;display:flex;gap:12px;flex-wrap:wrap}
    .w-280{width:280px;max-width:100%}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero d-flex align-items-center justify-content-between">
      <h1>Thanh toán đơn hàng</h1>
      <span class="badge rounded-pill bg-{{ status_cls }} text-uppercase">{{ status }}</span>
    </div>

    <div class="cardx mt-3">
      <div class="row g-0">
        <div class="col-md-5 thumb"><img src="{{ img_url }}" alt="Ảnh"></div>
        <div class="col-md-7">
          <div class="info">
            <div class="kv"><span class="text-muted">Mã giao dịch</span><b>#{{ pid }}</b></div>
            <div class="kv"><span class="text-muted">Số đơn hàng</span><b>#{{ order_id }}</b></div>
            <div class="kv"><span class="text-muted">Số tiền</span><b>{{ "{:,.0f}".format(amount) }} VND</b></div>
            <div class="kv"><span class="text-muted">Nhà cung cấp thanh toán</span><span>{{ provider }}</span></div>
            <div class="kv">
              <span class="text-muted">Hình thức thanh toán</span>
              <div class="d-flex align-items-center gap-2">
                <select id="methodSel" class="form-select form-select-sm w-280">
                  <option value="e-wallet" {% if method == "e-wallet" %}selected{% endif %}>Ví điện tử</option>
                  <option value="banking" {% if method == "banking" %}selected{% endif %}>Ngân hàng</option>
                  <option value="cash"    {% if method == "cash" %}selected{% endif %}>Tiền mặt</option>
                </select>
                <button id="btnSaveMethod" class="btn btn-outline-primary btn-sm">Lưu</button>
              </div>
            </div>
          </div>
          <div class="actions">
            <button id="btnPay" class="btn btn-primary px-4 flex-grow-1" data-bs-toggle="modal" data-bs-target="#invoiceModal">
              ✅ Tạo hóa đơn
            </button>
            <a href="http://localhost:8000/" class="btn btn-light">← Trang chủ</a>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Modal nhập thông tin hóa đơn -->
  <div class="modal fade" id="invoiceModal" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-lg modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header"><h5 class="modal-title">Thông tin hóa đơn</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
        <div class="modal-body">
          <form id="invoiceForm" class="row g-3">
            <div class="col-md-6"><label class="form-label">Họ và tên *</label><input name="full_name" class="form-control" required></div>
            <div class="col-md-6"><label class="form-label">Số điện thoại *</label><input name="phone" class="form-control" required></div>
            <div class="col-md-6"><label class="form-label">Email *</label><input name="email" type="email" class="form-control" required></div>
            <div class="col-md-6"><label class="form-label">Mã số thuế (tuỳ chọn)</label><input name="tax_code" class="form-control"></div>
            <div class="col-12"><label class="form-label">Địa chỉ nhận hóa đơn *</label><input name="address" class="form-control" required></div>
            <div class="col-md-4"><label class="form-label">Tỉnh/Thành *</label><input name="province" class="form-control" required></div>
            <div class="col-md-4"><label class="form-label">Quận/Huyện *</label><input name="district" class="form-control" required></div>
            <div class="col-md-4"><label class="form-label">Phường/Xã *</label><input name="ward" class="form-control" required></div>
            <div class="col-md-6">
              <label class="form-label">Hình thức thanh toán</label>
              <select id="methodInModal" name="method" class="form-select">
                <option value="e-wallet" {% if method == "e-wallet" %}selected{% endif %}>Ví điện tử</option>
                <option value="banking" {% if method == "banking" %}selected{% endif %}>Ngân hàng</option>
                <option value="cash"    {% if method == "cash" %}selected{% endif %}>Tiền mặt</option>
              </select>
            </div>
            <div class="col-12"><label class="form-label">Ghi chú</label><textarea name="note" class="form-control" rows="2"></textarea></div>
          </form>
          <div id="msg" class="text-danger small mt-2"></div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" data-bs-dismiss="modal">Đóng</button>
          <button id="btnConfirm" class="btn btn-primary">Tạo hóa đơn</button>
        </div>
      </div>
    </div>
  </div>

  <div class="toast-container">
    <div id="t1" class="toast align-items-center text-bg-success border-0">
      <div class="d-flex">
        <div class="toast-body" id="t1body">Đã lưu hình thức thanh toán.</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
  <script>
    const sel = document.getElementById('methodSel');
    const selModal = document.getElementById('methodInModal');
    sel.addEventListener('change', ()=> { selModal.value = sel.value; });

    document.getElementById('btnSaveMethod').onclick = async () => {
      const btn = document.getElementById('btnSaveMethod');
      btn.disabled = true; btn.textContent = 'Đang lưu...';
      try{
        const res = await fetch('/payment/update_method/{{ pid }}', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ method: sel.value })
        });
        const data = await res.json();
        if(res.ok){
          selModal.value = sel.value;
          document.getElementById('t1body').textContent = 'Đã lưu hình thức: ' + data.method;
          new bootstrap.Toast(document.getElementById('t1')).show();
        }else{ alert('Lỗi: ' + (data.error || 'Không lưu được.')); }
      }catch(e){ alert('Lỗi kết nối.'); }
      finally{ btn.disabled = false; btn.textContent = 'Lưu'; }
    };

    document.getElementById('btnConfirm').onclick = async () => {
      const form = document.getElementById('invoiceForm');
      if(!form.reportValidity()) return;
      const fd = new FormData(form);
      const payload = Object.fromEntries(fd.entries());
      const btn = document.getElementById('btnConfirm');
      const msg = document.getElementById('msg');
      btn.disabled = true; msg.textContent = 'Đang xử lý...';
      try{
        const res = await fetch('/payment/confirm/{{ pid }}', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if(res.ok){ window.location = data.invoice_url; }
        else{ msg.textContent = data.error || 'Không tạo được hóa đơn.'; btn.disabled = false; }
      }catch(e){ msg.textContent = 'Lỗi kết nối.'; btn.disabled = false; }
    };
  </script>
</body>
</html>
    """
    return render_template_string(
        html,
        pid=pay.id,
        order_id=pay.order_id,
        amount=pay.amount,
        method=pay.method.value,
        provider=pay.provider,
        status=pay.status.value,
        status_cls=status_cls,
        img_url=img_url,
    )

# ---------- 6b) Invoice page (chi tiết + QR mở HĐ; bấm xác nhận mới hiện QR thanh toán/STK) ----------
@bp.get("/payment/invoice/<int:cid>")
def invoice_page(cid: int):
    c = Contract.query.get(cid)
    if not c: return err("contract_not_found", 404)
    pay = Payment.query.get(c.payment_id)
    if not pay: return err("payment_not_found", 404)

    # đảm bảo đã có HĐ để mở bản in
    buyer = _parse_kv_from_contract(c)
    c_full = Contract.query.filter(
        Contract.payment_id==pay.id,
        Contract.title.ilike("%HỢP ĐỒNG MUA BÁN XE%")
    ).first()
    if not c_full:
        c_full = Contract(
            payment_id=pay.id,
            title="HỢP ĐỒNG MUA BÁN XE",
            content=_generate_vehicle_sale_contract(pay, buyer),
            created_at=datetime.utcnow()
        )
        db.session.add(c_full); commit_or_rollback()

    full_name = buyer["full_name"]; phone = buyer["phone"]; email = buyer["email"]
    address   = buyer["address"]; tax_code = buyer["tax_code"]; note = buyer["note"]

    try: VAT_RATE = float(os.getenv("VAT_RATE", "0.10"))
    except Exception: VAT_RATE = 0.10
    subtotal = int(pay.amount); vat = int(round(subtotal * VAT_RATE)); grand = subtotal + vat

    def vnd(n): return f"{n:,.0f} VND".replace(",", ",")

    status = pay.status.value
    status_cls = "success" if status == "paid" else ("warning" if status == "pending" else "secondary")

    html = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <title>Hóa đơn thanh toán #{{ cid }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root{ --brand:#0d47a1; --border:#e5e7eb; --muted:#64748b; }
    *{font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
    body{background:#f6f7fb}
    .container-invoice{max-width:1120px;margin:34px auto}
    .sheet{position:relative;background:#fff;border-radius:18px;box-shadow:0 14px 36px rgba(2,6,23,.08);padding:28px}
    .card-lite{border:1px solid var(--border);border-radius:14px;padding:14px 16px;background:#fbfcff}
    .card-pay{border:1px solid var(--border);border-radius:14px;padding:14px 16px;background:#f5f9ff}
    .totals{border:1px dashed var(--border);border-radius:14px;padding:12px 14px;background:#fff}
    .stamp{font-weight:700;color:var(--brand);border:2px solid var(--brand);padding:2px 8px;border-radius:6px}
    .table-items td,.table-items th{vertical-align:middle}
    .watermark{position:absolute;inset:0;pointer-events:none;display:flex;align-items:center;justify-content:center;opacity:.08}
    .watermark .txt{font-size:120px;font-weight:800;color:#16a34a;transform:rotate(-18deg);letter-spacing:8px}
    @media print{ .no-print{display:none!important} body{background:#fff} .sheet{box-shadow:none;border-radius:0} }
  </style>
</head>
<body>
  <div class="container-invoice">
    <div class="sheet">
      {% if status == "paid" %}<div class="watermark"><div class="txt">PAID</div></div>{% endif %}

      <!-- Header -->
      <div class="d-flex justify-content-between align-items-start">
        <div class="d-flex align-items-center gap-2">
          <img style="height:34px" src="https://img.icons8.com/?size=100&id=11392&format=png&color=0d47a1" alt="EV">
          <div>
            <div class="fw-bold fs-5" style="color:#0d47a1">EV & Battery • Payment Service</div>
            <div class="text-muted small">https://ev-battery.local • support@evbattery.test</div>
          </div>
        </div>
        <div class="text-end no-print">
          <div class="mb-2"><span class="badge bg-{{ status_cls }} text-uppercase">{{ status }}</span></div>
          <button onclick="window.print()" class="btn btn-outline-primary btn-sm">In / Lưu PDF</button>
        </div>
      </div>

      <hr class="my-3"/>

      <!-- Transaction blocks -->
      <div class="row g-3">
        <div class="col-md-6">
          <div class="fw-semibold mb-2">Thông tin giao dịch</div>
          <div class="card-lite px-3 py-2">
            <div class="row g-2">
              <div class="col-6">
                <div class="text-muted">Số hóa đơn</div>
                <div class="fw-semibold">{{ cid }}</div>
              </div>
              <div class="col-6 text-end">
                <div class="text-muted">Ngày lập hóa đơn</div>
                <div class="fw-semibold">{{ c.created_at.strftime("%d/%m/%Y %H:%M:%S") }}</div>
              </div>
            </div>
            <hr class="my-2">
            <div class="row g-2">
              <div class="col-6">
                <div class="text-muted">Số đơn hàng</div>
                <div class="fw-semibold">{{ pay.order_id }}</div>
              </div>
              <div class="col-6 text-end">
                <div class="text-muted">Mã giao dịch</div>
                <div class="fw-semibold">{{ pay.id }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="col-md-6">
          <div class="fw-semibold mb-2">Bên bán</div>
          <div class="card-lite">
            <div><b>EV & Battery Platform</b></div>
            <div class="text-muted">MST: 0123456789</div>
            <div class="text-muted">Địa chỉ: 01 Sample Rd, Q1, TP.HCM</div>
          </div>
        </div>
      </div>

      <div class="row g-3 mt-1">
        <div class="col-md-6">
          <div class="fw-semibold mb-2">Bên mua (người nhận hóa đơn)</div>
          <div class="card-lite">
            <div><b>{{ full_name }}</b></div>
            <div class="text-muted">{{ address }}</div>
            <div class="text-muted">MST: {{ tax_code }}</div>
            <div class="text-muted">Điện thoại: {{ phone }} • Email: {{ email }}</div>
          </div>
        </div>
        <div class="col-md-6">
          <div class="fw-semibold mb-2">Thanh toán</div>
          <div class="card-pay d-flex justify-content-between align-items-start gap-3">
            <div>
              <div><b>Số tiền:</b> {{ vnd(pay.amount) }} (+VAT {{ vnd(vat) }})</div>
              <div><b>Hình thức:</b> {{ pay.method.value }}</div>
              <div><b>Nhà cung cấp:</b> {{ pay.provider }}</div>
              <button id="btnShowQR" class="btn btn-primary btn-sm mt-2">Xác nhận thanh toán</button>
            </div>
            <div class="text-center">
              <div class="text-muted small mb-1">QR mở hợp đồng</div>
              <div id="qrcodeContract" style="width:98px;height:98px;border:1px solid #e2e8f0;border-radius:8px;"></div>
              <a class="small d-block mt-1" href="/payment/contract/preview/{{ c_full.id }}" target="_blank">Mở bản in</a>
            </div>
          </div>
        </div>
      </div>

      <!-- Items -->
      <div class="fw-semibold mt-4 mb-2">Chi tiết đơn hàng</div>
      <div class="table-responsive">
        <table class="table table-items align-middle">
          <thead>
            <tr>
              <th style="width:55%">Mô tả</th>
              <th style="width:15%" class="text-end">Số lượng</th>
              <th style="width:15%" class="text-end">Đơn giá</th>
              <th style="width:15%" class="text-end">Thành tiền</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Xe/Thiết bị EV/Battery – Đơn hàng <span class="stamp">#{{ pay.order_id }}</span></td>
              <td class="text-end">1</td>
              <td class="text-end">{{ vnd(subtotal) }}</td>
              <td class="text-end">{{ vnd(subtotal) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Totals -->
      <div class="row g-3 align-items-start">
        <div class="col-md-7">
          {% if note %}<div class="fw-semibold mb-2">Ghi chú</div><div class="card-lite">{{ note }}</div>{% endif %}
        </div>
        <div class="col-md-5">
          <div class="totals">
            <div class="d-flex justify-content-between"><div>Tạm tính</div><div>{{ vnd(subtotal) }}</div></div>
            <div class="d-flex justify-content-between"><div>VAT ({{ (VAT_RATE*100)|round(0) }}%)</div><div>{{ vnd(vat) }}</div></div>
            <hr class="my-2"/>
            <div class="d-flex justify-content-between fw-bold"><div>THANH TOÁN</div><div>{{ vnd(grand) }}</div></div>
          </div>
        </div>
      </div>

      <div class="text-muted small mt-3">© Payment Service</div>
    </div>
  </div>

<!-- Modal QR/Cash (đẹp hơn + đóng về trang chủ) -->
<div class="modal fade" id="payQRModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-lg modal-dialog-centered">
    <div class="modal-content" style="border-radius:16px; overflow:hidden">
      <div class="modal-header" style="background:#0d47a1;color:#fff">
        <div class="d-flex align-items-center gap-2">
          <span class="badge bg-light text-dark">PAY</span>
          <h5 class="modal-title mb-0">Thanh toán</h5>
        </div>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>

      <div class="modal-body">
        <!-- Tiền mặt -->
        <div id="cashNotice" class="alert alert-success d-none mb-0" style="border-radius:12px">
          <div class="fw-semibold mb-1">Đơn hàng đang được xác nhận.</div>
          <div>Cảm ơn bạn đã đặt hàng! Nhân viên sẽ liên hệ để thu tiền mặt và hoàn tất giao dịch.</div>
        </div>

        <!-- QR/STK -->
        <div id="qrBlock" class="row g-4 align-items-center d-none">
          <div class="col-md-7">
            <div class="d-flex align-items-center flex-wrap gap-2 mb-2">
              <span class="badge text-bg-primary">Số tiền</span>
              <span id="amt" class="fs-5 fw-bold"></span>
              <span class="badge text-bg-secondary ms-2" id="methodTxt"></span>
            </div>

            <div class="p-3 rounded-3" style="background:#f8fafc;border:1px solid #e5e7eb">
              <div class="mb-1"><b>Chuyển khoản tới:</b> <span id="bankName"></span></div>
              <div class="mb-1">STK: <span id="bankAcc" class="copyable" title="Sao chép"></span></div>
              <div class="mb-1">Chủ TK: <span id="bankOwner"></span></div>
              <div class="mb-1">Nội dung: <span id="memo" class="copyable" title="Sao chép"></span></div>
              <div class="text-muted small mt-2">
                * Sau khi chuyển khoản thành công, hệ thống sẽ ghi nhận khi có biên nhận
                (hoặc dùng endpoint <code>/payment/webhook/demo</code> để mô phỏng).
              </div>
            </div>
          </div>
          <div class="col-md-5">
            <div class="text-center">
              <div class="text-muted small mb-2">Quét QR để thanh toán</div>
              <div id="qrBox" style="width:180px;height:180px;margin:0 auto;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 10px 24px rgba(2,6,23,.08)"></div>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer bg-light-subtle">
        <button id="btnCloseModal" class="btn btn-primary px-4">Đóng</button>
      </div>
    </div>
  </div>
</div>

<style>
  .copyable{cursor:pointer;border-bottom:1px dashed #cbd5e1}
  .copyable:active{opacity:.7}
</style>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
  <script>
    // QR mở HỢP ĐỒNG (preview)
    new QRCode(document.getElementById('qrcodeContract'), {
      text: window.location.origin + "/payment/contract/preview/{{ c_full.id }}",
      width: 98, height: 98, correctLevel: QRCode.CorrectLevel.M
    });

    // Nút xác nhận thanh toán -> hiện QR/STK hoặc thông báo tiền mặt
    document.getElementById('btnShowQR')?.addEventListener('click', async ()=>{
      const res = await fetch('/payment/confirm/{{ pay.id }}', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({})});
      const data = await res.json();
      const qrm = new bootstrap.Modal(document.getElementById('payQRModal'));
      const qrBlock = document.getElementById('qrBlock');
      const cashNotice = document.getElementById('cashNotice');
      qrBlock.classList.add('d-none'); cashNotice.classList.add('d-none');
      document.getElementById('qrBox').innerHTML = '';
      if(res.ok && data.next_action === 'show_qr'){
        qrBlock.classList.remove('d-none');
        document.getElementById('amt').textContent = data.payment_info.grand_vnd;
        document.getElementById('methodTxt').textContent = data.payment_info.method;
        document.getElementById('bankName').textContent = data.payment_info.bank_name;
        document.getElementById('bankAcc').textContent  = data.payment_info.bank_account;
        document.getElementById('bankOwner').textContent= data.payment_info.bank_owner;
        document.getElementById('memo').textContent     = data.payment_info.memo;
        new QRCode(document.getElementById('qrBox'), {text: data.payment_info.qr_text, width: 140, height: 140, correctLevel: QRCode.CorrectLevel.M});
      }else{
        cashNotice.classList.remove('d-none');
      }
      qrm.show();
    });

  </script>                                                                                                                                  
<script>
  // Copy nhanh STK / nội dung CK
  document.addEventListener('click', async (e) => {
    const el = e.target.closest('.copyable');
    if(!el) return;
    try {
      await navigator.clipboard.writeText(el.textContent.trim());
      const old = el.getAttribute('title') || '';
      el.setAttribute('title', 'Đã sao chép!');
      setTimeout(()=> el.setAttribute('title', old || 'Sao chép'), 1200);
    } catch {}
  });

  // Đóng modal => quay về trang chủ
  const HOME_URL = 'http://localhost:8000/';  // muốn quay lại trang hiện tại thì đổi thành '/'
  let closeByButton = false;
  document.getElementById('btnCloseModal')?.addEventListener('click', () => {
    closeByButton = true;
    const m = bootstrap.Modal.getInstance(document.getElementById('payQRModal'));
    m?.hide();
  });
  document.getElementById('payQRModal')?.addEventListener('hidden.bs.modal', () => {
    if(closeByButton) window.location.href = HOME_URL;
  });
</script>

</body>
</html>
    """
    return render_template_string(
        html,
        cid=cid, c=c, pay=pay, c_full=c_full,
        full_name=full_name, phone=phone, email=email, address=address, tax_code=tax_code, note=note,
        subtotal=subtotal, vat=vat, grand=grand, VAT_RATE=VAT_RATE, vnd=vnd,
        status=status, status_cls=status_cls
    )

# ---------- 7) Confirm (idempotent) ----------
@bp.post("/payment/confirm/<int:pid>")
def confirm_and_pay(pid: int):
    pay = Payment.query.get(pid)
    if not pay: return err("payment_not_found", 404)

    data = request.get_json(silent=True) or {}

    # tìm invoice gần nhất
    c_invoice = Contract.query.filter(
        Contract.payment_id==pay.id,
        Contract.title.ilike("Hóa đơn/Contract%")
    ).order_by(Contract.id.desc()).first()

    if not c_invoice:
        # lần đầu: cần form
        required = ["full_name", "phone", "email", "address", "province", "district", "ward"]
        miss = [k for k in required if not data.get(k)]
        if miss: return err("missing fields: " + ", ".join(miss), 400)

        method_in = data.get("method")
        if method_in:
            try: pay.method = PaymentMethod(method_in)
            except Exception: return err("invalid_method", 400)

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
        c_invoice = Contract(
            payment_id=pay.id,
            title=f"Hóa đơn/Contract cho Payment #{pay.id}",
            content="\n".join(lines),
            created_at=datetime.utcnow()
        )
        db.session.add(c_invoice); commit_or_rollback()

        # luôn sinh HĐ để hóa đơn có QR mở bản in
        buyer = _parse_kv_from_contract(c_invoice)
        c_full = Contract.query.filter(
            Contract.payment_id==pay.id,
            Contract.title.ilike("%HỢP ĐỒNG MUA BÁN XE%")
        ).first()
        if not c_full:
            db.session.add(Contract(
                payment_id=pay.id,
                title="HỢP ĐỒNG MUA BÁN XE",
                content=_generate_vehicle_sale_contract(pay, buyer),
                created_at=datetime.utcnow()
            ))
            commit_or_rollback()

    # trả thông tin QR/STK (không set PAID ở bước này)
    try: VAT_RATE = float(os.getenv("VAT_RATE", "0.10"))
    except Exception: VAT_RATE = 0.10
    subtotal = int(pay.amount); vat = int(round(subtotal * VAT_RATE)); grand = subtotal + vat

    BANK_NAME    = os.getenv("BANK_NAME", "Vietcombank")
    BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "0123456789")
    BANK_OWNER   = os.getenv("BANK_OWNER", "EV & Battery Platform")
    MEMO         = f"PAY{pay.id}-ORD{pay.order_id}"
    QR_TEXT      = f"{BANK_NAME} | STK:{BANK_ACCOUNT} | CTK:{BANK_OWNER} | ND:{MEMO} | AMT:{grand}"

    next_action = "show_qr" if pay.method in (PaymentMethod.BANKING, PaymentMethod.E_WALLET) else "show_cash_notice"

    return ok({
        "message": "invoice_ready",
        "status": pay.status.value,
        "invoice_url": f"/payment/invoice/{c_invoice.id}",
        "next_action": next_action,
        "payment_info": {
            "method": pay.method.value,
            "amount_vnd": f"{subtotal:,.0f} VND",
            "vat_vnd": f"{vat:,.0f} VND",
            "grand_vnd": f"{grand:,.0f} VND",
            "bank_name": BANK_NAME,
            "bank_account": BANK_ACCOUNT,
            "bank_owner": BANK_OWNER,
            "memo": MEMO,
            "qr_text": QR_TEXT
        }
    })

# ---------- 8) Update method ----------
@bp.post("/payment/update_method/<int:pid>")
def update_method(pid: int):
    pay = Payment.query.get(pid)
    if not pay: return err("payment_not_found", 404)
    data = request.get_json(silent=True) or {}
    method = data.get("method")
    if method not in [m.value for m in PaymentMethod]:
        return err("invalid_method", 400)
    pay.method = PaymentMethod(method)
    commit_or_rollback()
    return ok({"message": "method_updated", "method": pay.method.value})
