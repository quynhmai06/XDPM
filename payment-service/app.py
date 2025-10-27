import os
from flask import Flask, jsonify, Response
from db import db
from routes import bp as payment_bp
from sqlalchemy import text

# ---- Factory ----
def create_app():
    app = Flask(__name__)

    # Lấy chuỗi kết nối từ docker-compose: postgresql+psycopg2://ev:evpass@db:5432/evdb
    # Nếu không có, chạy SQLite local cho dev
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///payment.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_AS_ASCII"] = False

    db.init_app(app)

    # Tạo bảng lần đầu (an toàn khi chạy nhiều lần)
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            # Không crash service nếu migration/bảng đã tồn tại
            print("[payment-service] create_all warning:", e)

    # Đăng ký blueprint cho các API /payment/...
    app.register_blueprint(payment_bp)

    # Health-check nhanh (liveness): chỉ báo service đang sống
    @app.get("/health")
    def health():
        return jsonify({"service": "payment_service", "status": "ok"}), 200

    # Readiness: kiểm tra DB đã sẵn sàng chưa
    @app.get("/ready")
    def ready():
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return jsonify({"ready": True}), 200
        except Exception as e:
            # Trả 503 để healthcheck hiểu là chưa sẵn sàng
            return jsonify({"ready": False, "error": str(e)}), 503

    # --- UI demo (đẹp, dùng Bootstrap) ---
    @app.get("/ui")
    def ui_page():
        html = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Payment Service Demo</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body{background:#f7f7fb}
    .card{border:0; border-radius:1rem; box-shadow:0 8px 20px rgba(0,0,0,.06)}
    .form-label{font-weight:600}
    .btn-primary{border-radius:.75rem}
  </style>
</head>
<body>
<div class="container py-4">
  <h3 class="mb-4">💳 Payment Service Demo</h3>
  <div class="row g-4">
    <!-- Create Payment -->
    <div class="col-lg-6">
      <div class="card p-3">
        <div class="card-body">
          <h5 class="card-title">Tạo thanh toán</h5>
          <div class="row g-3">
            <div class="col-6">
              <label class="form-label">Order ID</label>
              <input id="orderId" class="form-control" value="1001"/>
            </div>
            <div class="col-6">
              <label class="form-label">Số tiền (VND)</label>
              <input id="amount" class="form-control" value="150000000"/>
            </div>
            <div class="col-6">
              <label class="form-label">Buyer ID</label>
              <input id="buyerId" class="form-control" value="501"/>
            </div>
            <div class="col-6">
              <label class="form-label">Seller ID</label>
              <input id="sellerId" class="form-control" value="302"/>
            </div>
            <div class="col-6">
              <label class="form-label">Phương thức</label>
              <select id="method" class="form-select">
                <option value="e-wallet" selected>E-Wallet</option>
                <option value="banking">Banking</option>
              </select>
            </div>
            <div class="col-6">
              <label class="form-label">Provider</label>
              <input id="provider" class="form-control" value="DemoPay"/>
            </div>
            <div class="col-12 d-grid mt-2">
              <button id="btnCreate" class="btn btn-primary btn-lg">Tạo thanh toán</button>
            </div>
            <div class="col-12">
              <div id="createMsg" class="text-muted small mt-2"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Contract -->
    <div class="col-lg-6">
      <div class="card p-3">
        <div class="card-body">
          <h5 class="card-title">Hợp đồng mua bán số hóa</h5>
          <div class="row g-3">
            <div class="col-12">
              <label class="form-label">Payment ID</label>
              <input id="c_paymentId" class="form-control" placeholder="ID từ bước thanh toán"/>
            </div>
            <div class="col-12">
              <label class="form-label">Tiêu đề</label>
              <input id="c_title" class="form-control" value="Hợp đồng mua bán xe điện"/>
            </div>
            <div class="col-12">
              <label class="form-label">Nội dung</label>
              <textarea id="c_content" class="form-control" rows="5">Bên A (Người bán) cam kết tình trạng pin theo mô tả; Bên B (Người mua) thanh toán đủ số tiền...</textarea>
            </div>
            <div class="col-12 d-grid">
              <button id="btnCreateContract" class="btn btn-dark">Tạo hợp đồng</button>
            </div>
            <div class="col-12">
              <label class="form-label mt-3">Contract ID</label>
              <input id="s_contractId" class="form-control" placeholder="ID hợp đồng vừa tạo"/>
            </div>
            <div class="col-12">
              <label class="form-label">Người ký</label>
              <input id="s_signer" class="form-control" value="Nguyễn Văn B"/>
            </div>
            <div class="col-12 d-grid">
              <button id="btnSign" class="btn btn-outline-primary">Ký điện tử</button>
            </div>
            <div class="col-12">
              <div id="contractMsg" class="text-muted small mt-2"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</div>
<script>
function j(url, opts){ return fetch(url, Object.assign({headers:{'Content-Type':'application/json'}}, opts||{})); }

document.getElementById('btnCreate').onclick = async () => {
  const payload = {
    order_id: parseInt(document.getElementById('orderId').value || 0),
    buyer_id: parseInt(document.getElementById('buyerId').value || 0),
    seller_id: parseInt(document.getElementById('sellerId').value || 0),
    amount: parseInt(document.getElementById('amount').value || 0),
    method: document.getElementById('method').value,
    provider: document.getElementById('provider').value
  };
  const r = await j('/payment/create', {method:'POST', body: JSON.stringify(payload)});
  const data = await r.json();
  if(r.ok){
    // API có trả checkout_url => redirect đúng yêu cầu
    window.location = data.checkout_url || ('/payment/checkout/' + data.payment_id);
  }else{
    document.getElementById('createMsg').innerText = JSON.stringify(data);
  }
};

document.getElementById('btnCreateContract').onclick = async () => {
  const pid = parseInt(document.getElementById('c_paymentId').value || 0);
  const payload = {
    payment_id: pid,
    title: document.getElementById('c_title').value,
    content: document.getElementById('c_content').value
  };
  const r = await j('/payment/contract/create', {method:'POST', body: JSON.stringify(payload)});
  const data = await r.json();
  if(r.ok){
    document.getElementById('s_contractId').value = data.contract_id;
    document.getElementById('contractMsg').innerText = 'Tạo hợp đồng thành công (ID ' + data.contract_id + ')';
  }else{
    document.getElementById('contractMsg').innerText = JSON.stringify(data);
  }
};

document.getElementById('btnSign').onclick = async () => {
  const cid = parseInt(document.getElementById('s_contractId').value || 0);
  const signer = document.getElementById('s_signer').value;
  const r = await j('/payment/contract/sign', {method:'POST', body: JSON.stringify({contract_id:cid, signer_name: signer})});
  const data = await r.json();
  if(r.ok){
    document.getElementById('contractMsg').innerText = 'Đã ký. JWT=' + data.signature_jwt.substring(0,40) + '...';
  }else{
    document.getElementById('contractMsg').innerText = JSON.stringify(data);
  }
};
</script>
</body>
</html>
        """
        return Response(html, mimetype="text/html")

    # Trang root: chuyển sang UI
    @app.get("/")
    def _root_redirect():
        return ('<meta http-equiv="refresh" content="0; url=/ui">', 302)

    return app


app = create_app()

if __name__ == "__main__":
    # Mặc định: 0.0.0.0:5003
    app.run(host="0.0.0.0", port=5003, debug=True)
