# app.py (GATEWAY) - FULL (đã sửa + bổ sung ADMIN_URL, admin bridge, admin_login)
import os
import uuid
import requests
from flask import (
    Flask, render_template, request, redirect, url_for,
    jsonify, session, flash, Response
)

# ====================== CẤU HÌNH DỊCH VỤ UPSTREAM ======================
AUTH_URL    = os.getenv("AUTH_URL", "http://auth_service:5001")
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payment_service:5003")
PAYMENT_PUBLIC_URL = os.getenv("PAYMENT_PUBLIC_URL", "http://localhost:5003")  # dùng khi muốn mở trực tiếp ngoài proxy
ADMIN_URL   = os.getenv("ADMIN_URL", "http://admin_service:5002")              # <-- BỔ SUNG

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("GATEWAY_SECRET", "dev-gateway-secret")


# ========================== DEMO CATALOG / PRODUCT ==========================
CATALOG = {
    1: {
        "id": 1,
        "title": "VinFast VF e34 2023 - Như mới",
        "price": 590_000_000,
        "seller_id": 302,
        "img": "/static/images/v1.jpg",
        "location": "TP. Hồ Chí Minh",
        "description": (
            "Xe VinFast VF e34 màu trắng, odo 8.000 km, pin ~95%.\n"
            "Bảo dưỡng chính hãng, không tai nạn; nội thất nỉ giữ gìn."
        ),
        "seller_info": {"name": "Nguyễn Văn A", "phone": "0901 234 567", "email": "nguyenvana@example.com"}
    },
    2: {
        "id": 2,
        "title": "Tesla Model 3 Standard Range Plus 2022",
        "price": 1_090_000_000,
        "seller_id": 888,
        "img": "/static/images/v3.jpg",
        "location": "Hà Nội",
        "description": (
            "Tesla Model 3 SR+ nhập Mỹ, odo 15.000 km, pin ~98%.\n"
            "Tình trạng xe đẹp; Autopilot cơ bản; hỗ trợ kiểm tra gara chỉ định."
        ),
        "seller_info": {"name": "Trần Thị B", "phone": "0912 888 333", "email": "tranthib@example.com"}
    },
}
def get_product(pid: int):
    return CATALOG.get(int(pid))


# =============================== HELPERS ===============================
def _proxy_json(method: str, url: str, payload=None, timeout=10):
    """Gọi HTTP tới upstream (Auth/Payment/Admin) và chuẩn hóa về (data, status_code)."""
    try:
        r = requests.request(method, url, json=payload, timeout=timeout)
        ct = (r.headers.get("content-type") or "").lower()
        data = r.json() if ct.startswith("application/json") else {"message": r.text}
        return data, r.status_code
    except requests.RequestException as e:
        return {"error": f"upstream_error:{type(e).__name__}"}, 502


def verify_via_auth(token: str):
    """
    Xác thực token bằng AUTH_URL/auth/me (đính kèm cả header & query).
    Trả về (payload, error_message).
    """
    if not token:
        return None, "Token rỗng."
    try:
        r = requests.get(
            f"{AUTH_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            params={"token": token},
            timeout=6,
        )
    except requests.RequestException:
        return None, "Không kết nối được Auth service."
    if r.status_code != 200:
        try:
            err = (r.json() or {}).get("error")
        except Exception:
            err = None
        return None, "Token không hợp lệ" + (f" ({err})" if err else "")
    try:
        return r.json(), None
    except Exception:
        return None, "Auth service trả về payload không hợp lệ."


# ================================ PAGES ================================
@app.get("/")
def home():
    return render_template("index.html")

@app.get("/policy")
def policy_page():
    return render_template("policy.html")

@app.get("/product/<int:pid>")
def product_detail(pid: int):
    p = get_product(pid)
    if not p:
        flash("Sản phẩm không tồn tại.", "error")
        return redirect(url_for("home"))
    return render_template("product.html", p=p)

# ✅ GIỮ ĐÚNG GIAO DIỆN THANH TOÁN: ui.html
@app.get("/payment/ui")
def payment_ui():
    return render_template("ui.html")


# ============================== AUTH PAGES ==============================
@app.get("/login")
def login_page():
    return render_template("login.html")

@app.post("/login")
def do_login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        flash("Vui lòng nhập đầy đủ thông tin.", "error")
        return redirect(url_for("login_page"))
    # Gọi auth/login để lấy token
    try:
        r = requests.post(f"{AUTH_URL}/auth/login",
                          json={"username": username, "password": password},
                          timeout=6)
    except requests.RequestException:
        flash("Không kết nối được Auth service.", "error")
        return redirect(url_for("login_page"))
    if not r.ok:
        try:
            msg = r.json().get("error")
        except Exception:
            msg = "Đăng nhập thất bại."
        flash(msg, "error")
        return redirect(url_for("login_page"))

    token = (r.json() or {}).get("access_token")
    if not token:
        flash("Auth service không trả về access_token.", "error")
        return redirect(url_for("login_page"))

    payload, err = verify_via_auth(token)
    if err:
        flash(err, "error")
        return redirect(url_for("login_page"))

    session["access_token"] = token
    session["user"] = payload
    flash("Đăng nhập thành công.", "success")
    next_url = request.args.get("next") or session.pop("next_after_login", None)
    return redirect(next_url or url_for("home"))

@app.get("/register")
def register_page():
    return render_template("register.html")

@app.post("/register")
def do_register():
    username = request.form.get("username", "").strip()
    email    = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm  = request.form.get("confirm_password", "")
    if not username or not email or not password:
        flash("Vui lòng nhập đủ Username/Email/Password.", "error")
        return redirect(url_for("register_page"))
    if password != confirm:
        flash("Mật khẩu xác nhận không khớp.", "error")
        return redirect(url_for("register_page"))
    try:
        r = requests.post(f"{AUTH_URL}/auth/register",
                          json={"username": username, "email": email, "password": password},
                          timeout=8)
    except requests.RequestException:
        flash("Không kết nối được Auth service.", "error")
        return redirect(url_for("register_page"))
    if r.status_code in (200, 201):
        flash("Đăng ký thành công! Mời đăng nhập.", "success")
        return redirect(url_for("login_page"))
    try:
        msg = r.json().get("error")
    except Exception:
        msg = "Đăng ký thất bại."
    flash(msg, "error")
    return redirect(url_for("register_page"))

@app.get("/logout")
def logout_page():
    session.clear()
    flash("Đã đăng xuất.", "success")
    return redirect(url_for("home"))


# ============================== ADMIN PAGES ==============================
def is_admin_session() -> bool:
    user = session.get("user")
    return bool(user and user.get("role") == "admin")

# Modal trong templates/admin.html POST tới route này
@app.post("/admin/login")
def admin_login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        flash("Vui lòng nhập đủ thông tin.", "error")
        return redirect(url_for("admin_page"))

    try:
        r = requests.post(f"{AUTH_URL}/auth/login",
                          json={"username": username, "password": password},
                          timeout=6)
    except requests.RequestException:
        flash("Không kết nối được Auth service.", "error")
        return redirect(url_for("admin_page"))

    if not r.ok:
        flash("Đăng nhập admin thất bại.", "error")
        return redirect(url_for("admin_page"))

    token = (r.json() or {}).get("access_token")
    payload, err = verify_via_auth(token)
    if err or not payload or payload.get("role") != "admin":
        flash("Tài khoản không có quyền quản trị.", "error")
        return redirect(url_for("admin_page"))

    session["access_token"] = token
    session["user"] = payload
    flash("Đăng nhập quản trị thành công.", "success")
    return redirect(url_for("admin_page"))

@app.get("/admin")
def admin_page():
    # Nếu chưa login admin -> đẩy qua login (hoặc để modal hiển thị thì vẫn render trang)
    if not is_admin_session():
        # Cho phép xem giao diện với dữ liệu giả, modal đăng nhập vẫn hoạt động
        pass

    users = []
    products = []
    transactions = []
    reviews = []

    # Thử gọi admin-service để lấy data (nếu có)
    try:
        # 1 endpoint tổng hợp, nếu service bạn có: /admin/data
        r = requests.get(f"{ADMIN_URL}/admin/data", timeout=5)
        if r.ok:
            data = r.json() or {}
            users = data.get("users") or users
            products = data.get("products") or products
            transactions = data.get("transactions") or transactions
    except Exception:
        pass

    # Fallback dữ liệu giả để bạn thấy UI ngay
    if not users:
        users = [
            {"id": 1, "username": "Nam", "email": "nam@example.com", "is_admin": True, "approved": True},
            {"id": 2, "username": "Mai", "email": "mai@example.com", "is_admin": False, "approved": False},
        ]
    if not products:
        products = [
            {"id": 10, "name": "Pin VinFast 45kWh", "owner": "Quân", "price": 35_000_000, "approved": False},
            {"id": 11, "name": "VF e34 2023", "owner": "Đạt", "price": 585_000_000, "approved": True},
        ]
    if not transactions:
        transactions = [
            {"id": 100, "product": "VF e34", "buyer": "Đạt", "date": "27/10/2025", "status": "Hoàn tất"},
        ]

    # Danh sách yêu cầu thanh toán chờ duyệt (nếu admin-service có)
    try:
        r2 = requests.get(f"{ADMIN_URL}/admin/review/payment?status=pending", timeout=5)
        if r2.ok:
            reviews = r2.json() or []
    except Exception:
        pass

    return render_template("admin.html",
                           users=users,
                           products=products,
                           transactions=transactions,
                           reviews=reviews)

# === Hành động với USER (template gọi url_for('approve_user') / url_for('delete_user')) ===
@app.post("/admin/approve_user/<int:user_id>")
def approve_user(user_id: int):
    if not is_admin_session():
        session["next_after_login"] = url_for("approve_user", user_id=user_id)
        return redirect(url_for("login_page"))
    try:
        headers = {
            "Authorization": f"Bearer {session.get('access_token','')}",
            "Content-Type": "application/json"
        }
        r = requests.patch(f"{AUTH_URL}/auth/users/{user_id}/status",
                           json={"status": "approved"}, headers=headers, timeout=6)
        flash("Đã duyệt tài khoản." if r.ok else "Duyệt thất bại.", "success" if r.ok else "error")
    except requests.RequestException:
        flash("Không kết nối được Auth service.", "error")
    return redirect(url_for("admin_page"))

@app.get("/admin/delete_user/<int:user_id>")
def delete_user(user_id: int):
    if not is_admin_session():
        session["next_after_login"] = url_for("delete_user", user_id=user_id)
        return redirect(url_for("login_page"))
    try:
        headers = {"Authorization": f"Bearer {session.get('access_token','')}"}
        r = requests.delete(f"{AUTH_URL}/auth/users/{user_id}", headers=headers, timeout=6)
        flash("Đã xoá tài khoản." if r.ok else "Xoá thất bại.", "success" if r.ok else "error")
    except requests.RequestException:
        flash("Không kết nối được Auth service.", "error")
    return redirect(url_for("admin_page"))

# === Hành động với PRODUCT (template có link /admin/approve/<id> và /admin/delete/<id>) ===
@app.get("/admin/approve/<int:pid>")
def admin_product_approve(pid: int):
    if not is_admin_session():
        session["next_after_login"] = url_for("admin_product_approve", pid=pid)
        return redirect(url_for("login_page"))
    try:
        # Chuẩn đoán: admin-service có endpoint kiểu này
        data, code = _proxy_json("POST", f"{ADMIN_URL}/admin/products/{pid}/approve")
        flash("Đã duyệt bài đăng." if code == 200 else (data.get("error") or "Duyệt thất bại."), "success" if code == 200 else "error")
    except Exception:
        flash("Không kết nối được admin-service.", "error")
    return redirect(url_for("admin_page"))

@app.get("/admin/delete/<int:pid>")
def admin_product_delete(pid: int):
    if not is_admin_session():
        session["next_after_login"] = url_for("admin_product_delete", pid=pid)
        return redirect(url_for("login_page"))
    try:
        data, code = _proxy_json("DELETE", f"{ADMIN_URL}/admin/products/{pid}")
        flash("Đã xoá bài đăng." if code in (200,204) else (data.get("error") or "Xoá thất bại."), "success" if code in (200,204) else "error")
    except Exception:
        flash("Không kết nối được admin-service.", "error")
    return redirect(url_for("admin_page"))

# === Bridge DUYỆT/TỪ CHỐI payment review (để gắn nút JS nếu bạn thêm vào template) ===
@app.post("/admin/api/review/<int:rid>/approve")
def gw_review_approve(rid: int):
    if not is_admin_session():
        return jsonify({"error": "unauthorized"}), 401
    try:
        data, code = _proxy_json("POST", f"{ADMIN_URL}/admin/review/payment/{rid}/approve", {"note": "ok"})
        return jsonify(data), code
    except Exception:
        return jsonify({"error": "admin_unreachable"}), 502

@app.post("/admin/api/review/<int:rid>/reject")
def gw_review_reject(rid: int):
    if not is_admin_session():
        return jsonify({"error": "unauthorized"}), 401
    try:
        data, code = _proxy_json("POST", f"{ADMIN_URL}/admin/review/payment/{rid}/reject", {"note": "no"})
        return jsonify(data), code
    except Exception:
        return jsonify({"error": "admin_unreachable"}), 502


# ================================ CART ================================
def _cart():
    return session.setdefault("cart", {})

def cart_items():
    items, total = [], 0
    for pid_str, qty in _cart().items():
        p = get_product(int(pid_str))
        if not p:
            continue
        line_total = p["price"] * qty
        items.append({**p, "qty": qty, "line_total": line_total})
        total += line_total
    return items, total

@app.get("/cart")
def cart_view():
    items, total = cart_items()
    return jsonify({"items": items, "total": total})

@app.post("/cart/add/<int:pid>")
def cart_add(pid: int):
    if not get_product(pid):
        return jsonify({"error": "not_found"}), 404
    qty = int(request.form.get("qty", 1))
    cart = _cart()
    cart[str(pid)] = cart.get(str(pid), 0) + qty
    session.modified = True
    return redirect(url_for("cart_view"))

@app.post("/cart/remove/<int:pid>")
def cart_remove(pid: int):
    _cart().pop(str(pid), None)
    session.modified = True
    return redirect(url_for("cart_view"))

@app.post("/cart/clear")
def cart_clear():
    session["cart"] = {}
    return redirect(url_for("cart_view"))

@app.post("/cart/checkout")
def cart_checkout():
    items, total = cart_items()
    if total <= 0:
        flash("Giỏ hàng trống.", "error")
        return redirect(url_for("cart_view"))
    payload = {
        "order_id": int(str(uuid.uuid4().int)[-9:]),
        "buyer_id": session.get("user", {}).get("id", 0),
        "seller_id": 0,  # escrow/platform
        "amount": total,
        "method": request.form.get("method", "e-wallet"),
        "provider": request.form.get("provider", "DemoPay"),
    }
    try:
        r = requests.post(f"{PAYMENT_URL}/payment/create", json=payload, timeout=8)
        if r.ok:
            session["cart"] = {}
            flash(f"Tạo thanh toán giỏ hàng thành công (payment_id={r.json().get('payment_id')}).", "success")
        else:
            flash("Tạo thanh toán giỏ hàng thất bại.", "error")
    except requests.RequestException:
        flash("Không kết nối được payment-service.", "error")
    return redirect(url_for("cart_view"))


# =========================== PAYMENT PROXY (ui.html) ===========================
# !!! RẤT QUAN TRỌNG: giữ nguyên path /payment/* đúng như JS trong ui.html !!!

# 1) Tạo payment (ui.html → POST /payment/create)
@app.post("/payment/create")
def gw_payment_create():
    payload = request.get_json(silent=True) or {}
    data, code = _proxy_json("POST", f"{PAYMENT_URL}/payment/create", payload)
    return jsonify(data), code  # trả về checkout_url/payment_id/status

# 2) Tạo hợp đồng (ui.html → POST /payment/contract/create)
@app.post("/payment/contract/create")
def gw_contract_create():
    payload = request.get_json(silent=True) or {}
    data, code = _proxy_json("POST", f"{PAYMENT_URL}/payment/contract/create", payload)
    return jsonify(data), code

# 3) Ký hợp đồng (ui.html → POST /payment/contract/sign)
@app.post("/payment/contract/sign")
def gw_contract_sign():
    payload = request.get_json(silent=True) or {}
    data, code = _proxy_json("POST", f"{PAYMENT_URL}/payment/contract/sign", payload)
    return jsonify(data), code

# 4) (tuỳ chọn) Xem hợp đồng
@app.get("/payment/contract/view/<int:cid>")
def gw_contract_view(cid: int):
    data, code = _proxy_json("GET", f"{PAYMENT_URL}/payment/contract/view/{cid}")
    return jsonify(data), code


# ===================== FLOW “MUA NGAY” → REDIRECT SANG PAYMENTS-SERVICE =====================
@app.post("/buy/<int:pid>")
def buy_now(pid: int):
    p = get_product(pid)
    if not p:
        flash("Sản phẩm không tồn tại.", "error")
        return redirect(url_for("product_detail", pid=pid))

    payload = {
        "order_id": int(str(uuid.uuid4().int)[-9:]),
        "buyer_id": int(session.get("user", {}).get("id", 501)),  # demo
        "seller_id": p["seller_id"],
        "amount": p["price"],
        "method": request.form.get("method", "e-wallet"),
        "provider": request.form.get("provider", "DemoPay"),
    }
    try:
        r = requests.post(f"{PAYMENT_URL}/payment/create", json=payload, timeout=10)
        if not r.ok:
            try:
                msg = (r.json() or {}).get("error", "Tạo thanh toán thất bại.")
            except Exception:
                msg = "Tạo thanh toán thất bại."
            flash(msg, "error")
            return redirect(url_for("product_detail", pid=pid))

        data = r.json() or {}
        payment_id = data.get("payment_id")
        if not payment_id:
            flash("Thiếu payment_id/checkout_url.", "error")
            return redirect(url_for("product_detail", pid=pid))

        # ✅ Giữ như yêu cầu: chuyển hẳn qua trang checkout của payments-service (cùng tab)
        return redirect(f"{PAYMENT_PUBLIC_URL}/payment/checkout/{payment_id}", code=302)

    except requests.RequestException:
        flash("Không kết nối được payment-service.", "error")
        return redirect(url_for("product_detail", pid=pid))


@app.get("/checkout/<int:pid>")
def checkout_proxy(pid: int):
    """
    Proxy trang checkout của payment-service về cho trình duyệt.
    (Giữ lại để nơi khác dùng nếu cần.)
    """
    try:
        r = requests.get(f"{PAYMENT_URL}/payment/checkout/{pid}", timeout=8)
    except Exception as e:
        return f"Không gọi được payment-service: {e}", 502

    content_type = r.headers.get("Content-Type", "text/html; charset=utf-8")
    return Response(r.text, status=r.status_code, headers={"Content-Type": content_type})


# ================================ MAIN ================================
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    app.run(host=host, port=port, debug=True)
