# gateway/app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
import os, requests, jwt

AUTH = os.getenv("AUTH_URL", "http://localhost:5001")
JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "dev"

@app.route("/", endpoint="home")
def home():
    # Trang chủ giao diện
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"], endpoint="login_page")
def login_page():
    if request.method == "POST":
        try:
            r = requests.post(
                f"{AUTH}/auth/login",
                json={
                    "username": request.form["username"],
                    "password": request.form["password"],
                },
                timeout=5,
            )
        except requests.RequestException:
            flash("Không kết nối được Auth service.", "error")
            return render_template("login.html")

        if r.ok:
            token = r.json().get("access_token")
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            except Exception:
                flash("Token không hợp lệ.", "error")
                return render_template("login.html")

            session["access_token"] = token
            session["user"] = payload
            flash("Đăng nhập thành công!", "success")
            return redirect(url_for("home"))
        else:
            flash("Sai tài khoản hoặc mật khẩu.", "error")

    # GET
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
                f"{AUTH}/auth/register",
                json={"username": username, "email": email, "password": password},
                timeout=5,
            )
        except requests.RequestException:
            flash("Không kết nối được Auth service.", "error")
            return render_template("register.html")

        if r.status_code == 201:
            flash("Đăng ký thành công! Chờ admin duyệt.", "success")
            return redirect(url_for("login_page"))
        else:
            msg = r.json().get("error", "Đăng ký thất bại.")
            flash(msg, "error")

    # GET
    return render_template("register.html")

@app.get("/logout", endpoint="logout_page")
def logout_page():
    session.clear()
    flash("Đã đăng xuất!", "success")
    return redirect(url_for("home"))

@app.route("/admin", endpoint="admin_page")
def admin_page():
    u = session.get("user")
    # yêu cầu đã đăng nhập & có role=admin
    if not u or u.get("role") != "admin":
        flash("Bạn cần đăng nhập bằng tài khoản admin.", "error")
        return redirect(url_for("login_page"))

    # TODO: sau này gọi sang listing/admin service để lấy dữ liệu thật
    return render_template("admin.html", users=[], products=[], transactions=[])


if __name__ == "__main__":
    app.run(port=8080, debug=True)
