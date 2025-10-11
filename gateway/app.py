from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os, requests, jwt

# ==== Upstream services ====
AUTH_URL     = os.getenv("AUTH_URL", "http://auth_service:5001")
PAYMENT_URL  = os.getenv("PAYMENT_URL", "http://payment_service:5003")  # <--- thêm
JWT_SECRET   = os.getenv("JWT_SECRET", "devsecret")
JWT_ALGOS    = ["HS256"]

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("GATEWAY_SECRET", "dev")

# ===== Helpers =====
def decode_token(token: str):
    return jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS)

def is_admin_session() -> bool:
    user = session.get("user")
    return bool(user and user.get("role") == "admin")

def _proxy_json(method: str, url: str, payload=None):
    """Proxy helper cho JSON requests (giữ nguyên status code & headers cơ bản)."""
    try:
        r = requests.request(method, url, json=payload, timeout=8)
        # Trả body JSON nếu có, không thì trả text
        content_type = r.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            return (r.json(), r.status_code)
        return ({"message": r.text}, r.status_code)
    except requests.RequestException as e:
        return ({"error": f"upstream error: {type(e).__name__}"}, 502)

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
        try:
            r = requests.post(f"{AUTH_URL}/auth/login",
                              json={"username": username, "password": password},
                              timeout=5)
        except requests.RequestException:
            flash("Không kết nối được Auth service.", "error")
            return render_template("login.html")

        if r.ok:
            token = r.json().get("access_token")
            payload = jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS)
            session["access_token"] = token
            session["user"] = payload
            next_url = request.args.get("next") or session.pop("next_after_login", None)
            if payload.get("role") == "admin":
                return redirect(next_url or url_for("admin_page"))
            return redirect(next_url or url_for("home"))
        flash("Sai tài khoản hoặc mật khẩu.", "error")
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
    token = r.json().get("access_token")
    if not token:
        flash("Auth service không trả về access_token.", "error")
        return redirect(url_for("admin_page"))
    try:
        payload = decode_token(token)
    except Exception:
        flash("Token không hợp lệ.", "error")
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

# ===== Payment & Digital Contract (proxy đến payment-service) =====
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

# ===== Dev mode =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
