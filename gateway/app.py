from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os, requests, uuid

# ==== Upstream services ====
AUTH_URL     = os.getenv("AUTH_URL", "http://auth_service:5001")
PAYMENT_URL  = os.getenv("PAYMENT_URL", "http://payment_service:5003")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("GATEWAY_SECRET", "dev")

# ==== Catalog demo ====
CATALOG = {
    1: {
        "id": 1,
        "title": "VinFast VF e34 2023 - Như mới",
        "price": 590_000_000,
        "seller_id": 302,
        "img": "/static/images/v1.jpg",
        "location": "TP. Hồ Chí Minh",
        "description": (
            "Xe VinFast VF e34 màu trắng, odo 8.000 km, pin còn 95% dung lượng.\n"
            "Bảo dưỡng chính hãng, không tai nạn, bao test tại hãng.\n"
            "Trang bị ADAS cơ bản, nội thất nỉ giữ gìn, 2 chìa khoá."
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
            "Tình trạng xe đẹp, không va chạm; Autopilot kích hoạt cơ bản.\n"
            "Hỗ trợ sang tên toàn quốc, có thể kiểm tra tại gara bên mua chỉ định."
        ),
        "seller_info": {"name": "Trần Thị B", "phone": "0912 888 333", "email": "tranthib@example.com"}
    },
}
def get_product(pid: int):
    return CATALOG.get(int(pid))

# ===== Helpers =====
def is_admin_session() -> bool:
    user = session.get("user")
    return bool(user and user.get("role") == "admin")

def _proxy_json(method: str, url: str, payload=None):
    try:
        r = requests.request(method, url, json=payload, timeout=8)
        if r.headers.get("content-type", "").startswith("application/json"):
            return (r.json(), r.status_code)
        return ({"message": r.text}, r.status_code)
    except requests.RequestException as e:
        return ({"error": f"upstream error: {type(e).__name__}"}, 502)

def verify_via_auth(token: str):
    """Xác thực token bằng AUTH_URL/auth/me, gửi cả header và query để tránh rơi header."""
    if not token:
        return None, "Token rỗng"
    try:
        r = requests.get(
            f"{AUTH_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            params={"token": token},   # <-- thêm gửi qua query
            timeout=5,
        )
    except requests.RequestException:
        return None, "Không kết nối được Auth service."
    if r.status_code != 200:
        # cố đọc chi tiết lỗi từ auth
        try:
            err = (r.json() or {}).get("error")
        except Exception:
            err = None
        return None, f"Token không hợp lệ" + (f" ({err})" if err else "")
    try:
        return r.json(), None
    except Exception:
        return None, "Auth service trả về payload không hợp lệ."

# ---- Cart helpers (lưu trong session) ----
def _cart():
    return session.setdefault("cart", {})

def cart_items():
    cart = _cart()
    items, total = [], 0
    for pid_str, qty in cart.items():
        p = get_product(int(pid_str))
        if not p: continue
        line_total = p["price"] * qty
        items.append({**p, "qty": qty, "line_total": line_total})
        total += line_total
    return items, total

# ===== UI =====
@app.route("/", endpoint="home")
def home():
    return render_template("index.html")

# ===== Auth & Admin =====
@app.route("/login", methods=["GET", "POST"], endpoint="login_page")
def login_page():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Vui lòng nhập đầy đủ thông tin.", "error")
            return render_template("login.html")

        # gọi auth/login để lấy token
        try:
            r = requests.post(f"{AUTH_URL}/auth/login",
                              json={"username": username, "password": password},
                              timeout=5)
        except requests.RequestException:
            flash("Không kết nối được Auth service.", "error")
            return render_template("login.html")

        if not r.ok:
            # cố đọc chi tiết lỗi từ auth
            msg = None
            try: msg = r.json().get("error")
            except Exception: pass
            flash(msg or "Đăng nhập thất bại.", "error")
            return render_template("login.html")

        token = (r.json() or {}).get("access_token")
        if not token:
            flash("Auth service không trả về access_token.", "error")
            return render_template("login.html")

        # ✅ không tự decode nữa — xác thực qua /auth/me
        payload, err = verify_via_auth(token)
        if err:
            flash(f"{err}.", "error")
            return render_template("login.html")

        session["access_token"] = token
        session["user"] = payload
        next_url = request.args.get("next") or session.pop("next_after_login", None)
        if payload.get("role") == "admin":
            return redirect(next_url or url_for("admin_page"))
        return redirect(next_url or url_for("home"))

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"], endpoint="register_page")
def register_page():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if password != confirm:
            flash("Mật khẩu xác nhận không khớp.", "error")
            return render_template("register.html")
        try:
            r = requests.post(f"{AUTH_URL}/auth/register",
                              json={"username": username, "email": email, "password": password},
                              timeout=5)
        except requests.RequestException:
            flash("Không kết nối được Auth service.", "error")
            return render_template("register.html")

        if r.status_code in (200, 201):
            flash("Đăng ký thành công! Vui lòng chờ admin duyệt.", "success")
            return redirect(url_for("login_page"))

        msg = r.json().get("error") if r.headers.get("content-type","").startswith("application/json") else None
        flash(msg or "Đăng ký thất bại.", "error")
    return render_template("register.html")

@app.get("/logout", endpoint="logout_page")
def logout_page():
    was_admin = is_admin_session()
    session.clear()
    flash("Đã đăng xuất!", "success")
    return redirect(url_for("admin_page") if was_admin else url_for("home"))

@app.route("/admin", methods=["GET"], endpoint="admin_page")
def admin_page():
    users, products, transactions = [], [], []
    if is_admin_session():
        try:
            headers = {"Authorization": f"Bearer {session['access_token']}"}
            r = requests.get(f"{AUTH_URL}/auth/admin/users", headers=headers, timeout=5)
            if r.ok and r.headers.get("content-type","").startswith("application/json"):
                users = r.json().get("data", [])
            else:
                flash("Không lấy được danh sách người dùng.", "error")
        except requests.RequestException:
            flash("Không kết nối được auth service.", "error")
    return render_template("admin.html",
                           users=users, products=products, transactions=transactions,
                           is_admin=is_admin_session())

@app.post("/admin/login", endpoint="admin_login")
def admin_login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        flash("Vui lòng nhập đầy đủ thông tin.", "error")
        return redirect(url_for("admin_page"))
    try:
        r = requests.post(f"{AUTH_URL}/auth/login",
                          json={"username": username, "password": password},
                          timeout=5)
    except requests.RequestException:
        flash("Không kết nối được Auth service.", "error")
        return redirect(url_for("admin_page"))
    if not r.ok:
        flash("Đăng nhập thất bại.", "error")
        return redirect(url_for("admin_page"))

    token = (r.json() or {}).get("access_token")
    if not token:
        flash("Auth service không trả về access_token.", "error")
        return redirect(url_for("admin_page"))

    payload, err = verify_via_auth(token)
    if err:
        flash(f"{err}.", "error")
        return redirect(url_for("admin_page"))

    if payload.get("role") != "admin":
        flash("Tài khoản không phải admin.", "error")
        return redirect(url_for("admin_page"))

    session["access_token"] = token
    session["user"] = payload
    flash("Đăng nhập admin thành công!", "success")
    return redirect(url_for("admin_page"))

@app.route("/admin/approve_user/<int:user_id>", methods=["POST", "GET"])
def approve_user(user_id):
    if not is_admin_session():
        session["next_after_login"] = url_for("approve_user", user_id=user_id)
        return redirect(url_for("login_page"))
    try:
        headers = {"Authorization": f"Bearer {session['access_token']}", "Content-Type": "application/json"}
        r = requests.patch(f"{AUTH_URL}/auth/users/{user_id}/status",
                           json={"status": "approved"}, headers=headers, timeout=5)
        flash("Đã duyệt tài khoản." if r.ok else "Duyệt thất bại.",
              "success" if r.ok else "error")
    except requests.RequestException:
        flash("Không kết nối được auth service.", "error")
    return redirect(url_for("admin_page"))

@app.get("/admin/delete_user/<int:user_id>", endpoint="delete_user")
def delete_user(user_id):
    if not is_admin_session():
        session["next_after_login"] = url_for("delete_user", user_id=user_id)
        return redirect(url_for("login_page"))
    try:
        headers = {"Authorization": f"Bearer {session['access_token']}", "Content-Type": "application/json"}
        r = requests.patch(f"{AUTH_URL}/auth/users/{user_id}/status",
                           json={"status": "locked"}, headers=headers, timeout=5)
        flash("Đã khóa tài khoản (thay cho xóa)." if r.ok else "Khóa tài khoản thất bại.",
              "success" if r.ok else "error")
    except requests.RequestException:
        flash("Không kết nối được auth service.", "error")
    return redirect(url_for("admin_page"))

# ===== Payment & Digital Contract (proxy) =====
@app.post("/api/payments/create")
def gw_pay_create():
    payload = request.get_json(silent=True) or {}
    data, code = _proxy_json("POST", f"{PAYMENT_URL}/payment/create", payload)
    return jsonify(data), code

@app.get("/api/payments/simulate/<int:pid>")
def gw_pay_sim(pid):
    data, code = _proxy_json("GET", f"{PAYMENT_URL}/payment/simulate/{pid}")
    return jsonify(data), code

@app.post("/api/contracts/create")
def gw_contract_create():
    payload = request.get_json(silent=True) or {}
    data, code = _proxy_json("POST", f"{PAYMENT_URL}/payment/contract/create", payload)
    return jsonify(data), code

@app.post("/api/contracts/sign")
def gw_contract_sign():
    payload = request.get_json(silent=True) or {}
    data, code = _proxy_json("POST", f"{PAYMENT_URL}/payment/contract/sign", payload)
    return jsonify(data), code

@app.get("/api/contracts/view/<int:cid>")
def gw_contract_view(cid):
    data, code = _proxy_json("GET", f"{PAYMENT_URL}/payment/contract/view/{cid}")
    return jsonify(data), code

# ===== Product detail / Cart =====
@app.get("/product/<int:pid>")
def product_detail(pid):
    p = get_product(pid)
    if not p:
        flash("Sản phẩm không tồn tại.", "error")
        return redirect(url_for("home"))
    return render_template("product.html", p=p)

@app.post("/buy/<int:pid>")
def buy_now(pid):
    p = get_product(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    payload = {
        "order_id": int(str(uuid.uuid4().int)[-9:]),
        "buyer_id": session.get("user", {}).get("id", 0),
        "seller_id": p["seller_id"],
        "amount": p["price"],
        "method": request.form.get("method", "e-wallet"),
        "provider": request.form.get("provider", "DemoPay"),
    }
    try:
        r = requests.post(f"{PAYMENT_URL}/payment/create", json=payload, timeout=8)
        if r.ok:
            flash(f"Tạo thanh toán thành công (payment_id={r.json().get('payment_id')}).", "success")
        else:
            flash("Tạo thanh toán thất bại.", "error")
    except requests.RequestException:
        flash("Không kết nối được payment-service.", "error")
    return redirect(url_for("product_detail", pid=pid))

@app.post("/cart/add/<int:pid>")
def cart_add(pid):
    if not get_product(pid):
        return jsonify({"error": "not found"}), 404
    cart = _cart()
    cart[str(pid)] = cart.get(str(pid), 0) + int(request.form.get("qty", 1))
    session.modified = True
    return redirect(url_for("cart_view"))

@app.post("/cart/remove/<int:pid>")
def cart_remove(pid):
    _cart().pop(str(pid), None)
    session.modified = True
    return redirect(url_for("cart_view"))

@app.post("/cart/clear")
def cart_clear():
    session["cart"] = {}
    return redirect(url_for("cart_view"))

@app.get("/cart")
def cart_view():
    items, total = cart_items()
    return render_template("cart.html", items=items, total=total)

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
