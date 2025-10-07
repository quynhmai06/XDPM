from flask import Flask, render_template, request, redirect, url_for, flash, session
import os, requests, jwt
from flask import jsonify

AUTH_URL = os.getenv("AUTH_URL", "http://127.0.0.1:5001")
JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
JWT_ALGOS = ["HS256"]

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("GATEWAY_SECRET", "dev")

def decode_token(token: str):
    return jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS)

def is_admin_session() -> bool:
    token = session.get("access_token")
    if not token:
        return False
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS)
        return payload.get("role") == "admin"
    except Exception:
        return False

@app.route("/", endpoint="home")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"], endpoint="login_page")
def login_page():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Vui lòng nhập đầy đủ thông tin.", "error")
            return render_template("login.html")

        try:
            r = requests.post(
                f"{AUTH_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=5,
            )
        except requests.RequestException:
            flash("Không kết nối được Auth service.", "error")
            return render_template("login.html")

        if r.ok:
            token = r.json().get("access_token")
            payload = decode_token(token)
            session["access_token"] = token
            # session['user'] chỉ dùng cho hiển thị UI
            session["user"] = {"username": payload.get("username"), "role": payload.get("role")}

            next_url = request.args.get("next") or session.pop("next_after_login", None)
            if payload.get("role") == "admin":
                return redirect(next_url or url_for("admin_page"))
            return redirect(next_url or url_for("home"))

        # Hiển thị thông báo theo mã lỗi từ auth_service
        msg = "Đăng nhập thất bại."
        if r.headers.get("content-type", "").startswith("application/json"):
            err = (r.json() or {}).get("error")
            if err == "invalid_credentials":
                msg = "Sai tài khoản hoặc mật khẩu."
            elif err == "not_approved":
                msg = "Tài khoản chưa được admin duyệt. Vui lòng chờ duyệt."
            elif err == "locked":
                msg = "Tài khoản đã bị khóa."
        flash(msg, "error")

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
            r = requests.post(
                f"{AUTH_URL}/auth/register",
                json={"username": username, "email": email, "password": password},
                timeout=5,
            )
        except requests.RequestException:
            flash("Không kết nối được Auth service.", "error")
            return render_template("register.html")

        if r.status_code in (200, 201):
            flash("Đăng ký thành công! Vui lòng chờ admin duyệt.", "success")
            return redirect(url_for("login_page"))

        msg = None
        if r.headers.get("content-type", "").startswith("application/json"):
            msg = r.json().get("error")
        flash(msg or "Đăng ký thất bại.", "error")

    return render_template("register.html")

@app.get("/logout", endpoint="logout_page")
def logout_page():
    session.clear()
    flash("Đã đăng xuất!", "success")
    return redirect(url_for("home"))

@app.route("/admin", methods=["GET"], endpoint="admin_page")
def admin_page():
    users, products, transactions = [], [], []

    if is_admin_session():
        try:
            headers = {"Authorization": f"Bearer {session['access_token']}"}
            r = requests.get(f"{AUTH_URL}/auth/admin/users", headers=headers, timeout=5)
            if r.ok and r.headers.get("content-type", "").startswith("application/json"):
                users = r.json().get("data", [])
            else:
                flash("Không lấy được danh sách người dùng.", "error")
        except requests.RequestException:
            flash("Không kết nối được auth service.", "error")

    return render_template(
        "admin.html",
        users=users,
        products=products,
        transactions=transactions,
        is_admin=is_admin_session()
    )

@app.post("/admin/login", endpoint="admin_login")
def admin_login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        flash("Vui lòng nhập đầy đủ thông tin.", "error")
        return redirect(url_for("admin_page"))

    try:
        r = requests.post(
            f"{AUTH_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=5,
        )
    except requests.RequestException:
        flash("Không kết nối được Auth service.", "error")
        return redirect(url_for("admin_page"))

    if not r.ok:
        # đọc thông báo lỗi cụ thể
        msg = "Đăng nhập thất bại."
        if r.headers.get("content-type", "").startswith("application/json"):
            err = (r.json() or {}).get("error")
            if err == "invalid_credentials":
                msg = "Sai tài khoản hoặc mật khẩu."
            elif err == "not_approved":
                msg = "Tài khoản chưa được admin duyệt. Vui lòng chờ duyệt."
            elif err == "locked":
                msg = "Tài khoản đã bị khóa."
        flash(msg, "error")
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
    session["user"] = {"username": payload.get("username"), "role": payload.get("role")}
    flash("Đăng nhập admin thành công!", "success")
    return redirect(url_for("admin_page"))

@app.route("/admin/approve_user/<int:user_id>", methods=["POST", "GET"])
def approve_user(user_id):
    if not is_admin_session():
        session["next_after_login"] = url_for("approve_user", user_id=user_id)
        return redirect(url_for("login_page"))
    try:
        headers = {"Authorization": f"Bearer {session['access_token']}", "Content-Type": "application/json"}
        r = requests.patch(
            f"{AUTH_URL}/auth/users/{user_id}/status",
            json={"status": "approved"},
            headers=headers,
            timeout=5,
        )
        flash("Đã duyệt tài khoản." if r.ok else "Duyệt thất bại.", "success" if r.ok else "error")
    except requests.RequestException:
        flash("Không kết nối được auth service.", "error")
    return redirect(url_for("admin_page"))

@app.route("/admin/delete_user/<int:user_id>", methods=["POST","GET"])
def delete_user(user_id):
    if not is_admin_session():
        # lưu lại nơi cần quay về sau khi login
        session["next_after_login"] = url_for("admin_page")
        return redirect(url_for("login_page"))

    try:
        headers = {
            "Authorization": f"Bearer {session['access_token']}",
            "Content-Type": "application/json",
        }
        r = requests.patch(
            f"{AUTH_URL}/auth/users/{user_id}/status",
            json={"status": "locked"},
            headers=headers,
            timeout=5,
        )
        flash("Đã khóa tài khoản." if r.ok else "Khóa tài khoản thất bại.",
              "success" if r.ok else "error")
    except requests.RequestException:
        flash("Không kết nối được auth service.", "error")

    return redirect(url_for("admin_page"))

@app.get("/admin/logout", endpoint="admin_logout")
def admin_logout():
    session.clear()
    flash("Đã đăng xuất khỏi Admin!", "success")
    return redirect(url_for("admin_page"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
