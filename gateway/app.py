from flask import Flask, render_template, request, redirect, url_for, flash, session
import os, requests, jwt
from flask import jsonify

AUTH_URL = os.getenv("AUTH_URL", "http://127.0.0.1:5001")
ADMIN_URL = os.getenv("ADMIN_URL", "http://127.0.0.1:5002")
LISTINGS_URL = os.getenv("LISTINGS_URL", "http://127.0.0.1:5003")
FAVORITES_URL = os.getenv("FAVORITES_URL", "http://127.0.0.1:5004")
ORDERS_URL = os.getenv("ORDERS_URL", "http://127.0.0.1:5005")
AUCTIONS_URL = os.getenv("AUCTIONS_URL", "http://127.0.0.1:5006")
REVIEWS_URL = os.getenv("REVIEWS_URL", "http://127.0.0.1:5007")
JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("GATEWAY_SECRET", "devsecret"))
JWT_ALGOS = ["HS256"]

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("GATEWAY_SECRET", "dev")

def decode_token(token: str):
    return jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS)

def is_admin_session() -> bool:
    user = session.get("user")
    return bool(user and user.get("role") == "admin")

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
    was_admin = is_admin_session()
    session.clear()
    flash("Đã đăng xuất!", "success")
    return redirect(url_for("admin_page") if was_admin else url_for("home"))

@app.route("/admin", methods=["GET"], endpoint="admin_page")
def admin_page():
    users = []
    products = []
    transactions = []

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

@app.get("/admin/delete_user/<int:user_id>", endpoint="delete_user")
def delete_user(user_id):
    if not is_admin_session():
        session["next_after_login"] = url_for("delete_user", user_id=user_id)
        return redirect(url_for("login_page"))
    try:
        headers = {"Authorization": f"Bearer {session['access_token']}", "Content-Type": "application/json"}
        r = requests.patch(
            f"{AUTH_URL}/auth/users/{user_id}/status",
            json={"status": "locked"},
            headers=headers,
            timeout=5,
        )
        if r.ok:
            flash("Đã khóa tài khoản (thay cho xóa).", "success")
        else:
            flash("Khóa tài khoản thất bại.", "error")
    except requests.RequestException:
        flash("Không kết nối được auth service.", "error")
    return redirect(url_for("admin_page"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

# ======= API proxy minimal endpoints =======
@app.get('/api/search/vehicles')
def api_search_vehicles():
    try:
        r = requests.get(f"{LISTINGS_URL}/listings/vehicles", params=request.args, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "listings_unavailable"}, 503

@app.get('/api/search/batteries')
def api_search_batteries():
    try:
        r = requests.get(f"{LISTINGS_URL}/listings/batteries", params=request.args, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "listings_unavailable"}, 503

@app.get('/api/favorites')
def api_favorites_list():
    user = session.get('user')
    if not user:
        return {"error": "unauthenticated"}, 401
    try:
        r = requests.get(f"{FAVORITES_URL}/favorites/me", params={"user_id": user['sub']}, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "favorites_unavailable"}, 503

@app.post('/api/favorites')
def api_favorites_add():
    user = session.get('user')
    if not user:
        return {"error": "unauthenticated"}, 401
    d = request.get_json(force=True)
    d['user_id'] = user['sub']
    try:
        r = requests.post(f"{FAVORITES_URL}/favorites", json=d, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "favorites_unavailable"}, 503

@app.post('/api/orders')
def api_orders_create():
    user = session.get('user')
    if not user:
        return {"error": "unauthenticated"}, 401
    d = request.get_json(force=True)
    d['buyer_id'] = user['sub']
    try:
        r = requests.post(f"{ORDERS_URL}/orders", json=d, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "orders_unavailable"}, 503

@app.get('/api/orders/history')
def api_orders_history():
    user = session.get('user')
    if not user:
        return {"error": "unauthenticated"}, 401
    try:
        r = requests.get(f"{ORDERS_URL}/orders/history", params={"user_id": user['sub'], "role": request.args.get('role','buyer')}, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "orders_unavailable"}, 503

@app.post('/api/auctions/<int:aid>/bid')
def api_bid(aid:int):
    user = session.get('user')
    if not user:
        return {"error": "unauthenticated"}, 401
    d = request.get_json(force=True)
    d['bidder_id'] = user['sub']
    try:
        r = requests.post(f"{AUCTIONS_URL}/auctions/{aid}/bid", json=d, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "auctions_unavailable"}, 503

@app.post('/api/auctions/<int:aid>/buy-now')
def api_buy_now(aid:int):
    try:
        r = requests.post(f"{AUCTIONS_URL}/auctions/{aid}/buy-now", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "auctions_unavailable"}, 503

@app.post('/api/reviews')
def api_reviews_create():
    user = session.get('user')
    if not user:
        return {"error": "unauthenticated"}, 401
    d = request.get_json(force=True)
    d['reviewer_id'] = user['sub']
    try:
        r = requests.post(f"{REVIEWS_URL}/reviews", json=d, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "reviews_unavailable"}, 503

@app.get('/api/reviews/user/<int:user_id>')
def api_reviews_list(user_id:int):
    try:
        r = requests.get(f"{REVIEWS_URL}/reviews/user/{user_id}", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "reviews_unavailable"}, 503
