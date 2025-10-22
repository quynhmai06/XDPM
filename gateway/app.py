from flask import Flask, render_template, redirect, url_for, request, session, flash
import os, requests, jwt
from functools import wraps

# ================== Config ==================
AUTH_URL = os.getenv("AUTH_URL", "http://127.0.0.1:5001")
ADMIN_URL = os.getenv("ADMIN_URL", "http://127.0.0.1:5003")
JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
JWT_ALGOS = ["HS256"]

app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")
app.secret_key = os.getenv("GATEWAY_SECRET", "dev")


# ================== Helpers ==================
def decode_token(token: str):
    return jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS)

def is_admin_session() -> bool:
    token = session.get("access_token")
    if not token:
        return False
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS)
        return str(payload.get("role", "")).lower() == "admin"
    except Exception:
        return False

def login_required(next_endpoint_name="login_page"):
    """Decorator: bắt buộc đăng nhập, nếu chưa => redirect login và nhớ 'next'."""
    def _wrap(f):
        @wraps(f)
        def inner(*args, **kwargs):
            token = session.get("access_token")
            if not token:
                # lưu route hiện tại để quay lại sau khi login
                session["next_after_login"] = url_for(request.endpoint, **(request.view_args or {}))
                return redirect(url_for(next_endpoint_name))
            return f(*args, **kwargs)
        return inner
    return _wrap


# ================== Routes ==================
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
            token = (r.json() or {}).get("access_token")
            if not token:
                flash("Auth service không trả về access_token.", "error")
                return render_template("login.html")
            try:
                payload = decode_token(token)
            except Exception:
                flash("Token không hợp lệ.", "error")
                return render_template("login.html")

            session["access_token"] = token
            session["user"] = {"username": payload.get("username"), "role": payload.get("role")}

            next_url = request.args.get("next") or session.pop("next_after_login", None)
            if str(payload.get("role", "")).lower() == "admin":
                return redirect(next_url or url_for("admin_page"))
            return redirect(next_url or url_for("home"))

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
                json={"username": username, "email": email, "password": password, "phone": request.form.get("phone", "")},
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
            msg = (r.json() or {}).get("error")
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
            r = requests.get(f"{ADMIN_URL}/admin/users", headers=headers, timeout=5)
            if r.ok and r.headers.get("content-type", "").startswith("application/json"):
                data = r.json().get("data", [])
                users = [u for u in data if not (u.get("is_admin") or str(u.get("role", "")).lower() == "admin")]
            else:
                flash("Không lấy được danh sách người dùng.", "error")
        except requests.RequestException:
            flash("Không kết nối được admin service.", "error")

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

    token = (r.json() or {}).get("access_token")
    if not token:
        flash("Auth service không trả về access_token.", "error")
        return redirect(url_for("admin_page"))

    try:
        payload = decode_token(token)
    except Exception:
        flash("Token không hợp lệ.", "error")
        return redirect(url_for("admin_page"))

    if str(payload.get("role", "")).lower() != "admin":
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
            f"{ADMIN_URL}/admin/users/{user_id}/status",
            json={"status": "approved"},
            headers=headers,
            timeout=5,
        )
        flash("Đã duyệt tài khoản." if r.ok else "Duyệt thất bại.", "success" if r.ok else "error")
    except requests.RequestException:
        flash("Không kết nối được admin service.", "error")
    return redirect(url_for("admin_page"))


@app.route("/admin/delete_user/<int:user_id>", methods=["POST","GET"])
def delete_user(user_id):
    if not is_admin_session():
        session["next_after_login"] = url_for("admin_page")
        return redirect(url_for("login_page"))

    try:
        headers = {
            "Authorization": f"Bearer {session['access_token']}",
            "Content-Type": "application/json",
        }
        r = requests.patch(
            f"{ADMIN_URL}/admin/users/{user_id}/status",
            json={"status": "locked"},
            headers=headers,
            timeout=5,
        )
        flash("Đã khóa tài khoản." if r.ok else "Khóa tài khoản thất bại.",
              "success" if r.ok else "error")
    except requests.RequestException:
        flash("Không kết nối được admin service.", "error")

    return redirect(url_for("admin_page"))


@app.get("/admin/logout", endpoint="admin_logout")
def admin_logout():
    session.clear()
    flash("Đã đăng xuất khỏi Admin!", "success")
    return redirect(url_for("admin_page"))


@app.route("/policy", methods=["GET"], endpoint="policy_page")
def policy_page():
    return render_template("policy.html")


@app.post("/change-password")
@login_required()
def change_password_gateway():
    """Forward form đổi mật khẩu sang auth-service"""
    token = session.get("access_token")
    form = {
        "current_password": request.form.get("current_password", ""),
        "new_password": request.form.get("new_password", ""),
    }
    try:
        r = requests.post(
            f"{AUTH_URL}/auth/change-password",
            params={"token": token},
            data=form,
            timeout=5,
        )
    except requests.RequestException:
        flash("Không kết nối được Auth service.", "error")
        return redirect(url_for("profile"))

    if r.status_code in (200, 302):
        flash("Đổi mật khẩu thành công.", "success")
    else:
        msg = "Đổi mật khẩu thất bại."
        if r.headers.get("content-type", "").startswith("application/json"):
            j = (r.json() or {})
            msg = j.get("message") or j.get("error") or msg
        flash(msg, "error")

    return redirect(url_for("profile"))


# ===== Profile page (giao diện) =====
# Đặt endpoint = "profile" để mọi {{ url_for('profile') }} trong template đều chạy được
@app.get("/profile", endpoint="profile")
@login_required() 
def profile_page():
    # Nếu bạn dùng file profile_only.html thì đổi tên file tại đây cho đúng:
    # return render_template("profile_only.html")
    return render_template("profile.html")


# ================== Main ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
