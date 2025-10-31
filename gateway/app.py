# gateway/app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os, requests, jwt, time, json
from werkzeug.utils import secure_filename
import re

def _num(x):
    if x is None: 
        return None
    m = re.search(r"\d+(?:\.\d+)?", str(x))
    return float(m.group(0)) if m else None


# ==== Config các service ====
AUTH_URL    = os.getenv("AUTH_URL",    "http://auth_service:5001")
LISTING_URL = os.getenv("LISTING_URL", "http://listing_service:5002")
PRICING_URL = os.getenv("PRICING_URL", "http://pricing_service:5003")

JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
JWT_ALGOS  = ["HS256"]

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("GATEWAY_SECRET", "dev")

# ==== Helpers JWT / Session ====
def decode_token(token: str):
    # Bỏ kiểm tra 'sub' phải là string (verify_sub=False)
    return jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS, options={"verify_sub": False})

def is_admin_session() -> bool:
    user = session.get("user")
    return bool(user and user.get("role") == "admin")

# ==== Upload image (gateway lưu ảnh, gửi URL sang listing-service) ====
UPLOAD_DIR = os.path.join(app.static_folder, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED = {"jpg", "jpeg", "png", "webp"}

def save_image(file_storage, prefix="img"):
    if not file_storage or file_storage.filename == "":
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return None
    fname = f"{prefix}_{int(time.time()*1000)}_{secure_filename(file_storage.filename)}"
    path = os.path.join(UPLOAD_DIR, fname)
    file_storage.save(path)
    return f"/static/uploads/{fname}"  # URL public

# ================== ROUTES ==================

@app.route("/", endpoint="home")
def home():
    cars = []
    batts = []
    try:
        # gọi xe điện
        r1 = requests.get(
            f"{LISTING_URL}/listings/?approved=1&product_type=car&sort=created_desc&per_page=12",
            timeout=5
        )
        if r1.ok and r1.headers.get("content-type","").startswith("application/json"):
            cars = r1.json().get("items", [])
    except requests.RequestException:
        cars = []

    try:
        # gọi pin xe điện
        r2 = requests.get(
            f"{LISTING_URL}/listings/?approved=1&product_type=battery&sort=created_desc&per_page=12",
            timeout=5
        )
        if r2.ok and r2.headers.get("content-type","").startswith("application/json"):
            batts = r2.json().get("items", [])
    except requests.RequestException:
        batts = []

    return render_template("index.html", cars=cars, batts=batts)


# ---------- Auth ----------
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
            try:
                payload = decode_token(token)
            except Exception:
                flash("Token không hợp lệ.", "error")
                return render_template("login.html")

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
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

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
            data = r.json()
            err = (data.get("error") or "").lower()
            if "exist" in err:
                msg = "Tên đăng nhập hoặc email đã tồn tại."
            elif "email" in err:
                msg = "Email không hợp lệ hoặc đã tồn tại."
            elif "username" in err:
                msg = "Tên đăng nhập không hợp lệ hoặc đã tồn tại."
        flash(msg or "Đăng ký thất bại.", "error")

    return render_template("register.html")

@app.get("/logout", endpoint="logout_page")
def logout_page():
    was_admin = is_admin_session()
    session.clear()
    flash("Đã đăng xuất!", "success")
    return redirect(url_for("admin_page") if was_admin else url_for("home"))

# ---------- Đăng tin (Member) ----------
@app.route("/listings/new", methods=["GET", "POST"])
def add_listing():
    u = session.get("user")
    if not u:
        session["next_after_login"] = url_for("add_listing")
        flash("Vui lòng đăng nhập để đăng tin.", "error")
        return redirect(url_for("login_page"))

    if request.method == "POST":
        payload = {
            "product_type": (request.form.get("product_type") or "car").strip(),
            "name": (request.form.get("name") or "").strip(),
            "description": (request.form.get("description") or "").strip(),
            "price": int(request.form.get("price") or 0),
            "brand": (request.form.get("brand") or "").strip(),
            "province": (request.form.get("province") or "").strip(),
            "year": int(request.form.get("year") or 0),
            "mileage": int(request.form.get("mileage") or 0),
            "battery_capacity": (request.form.get("battery_capacity") or "").strip(),
        }
        if not payload["name"] or payload["price"] <= 0:
            flash("Nhập các thông tin bắt buộc!", "error")
            return render_template("post_product.html")

        # Lưu ảnh tại gateway
        main_url = save_image(request.files.get("main_image"), prefix=f"{u['username']}_main")
        sub_urls = []
        for f in request.files.getlist("sub_images"):
            url = save_image(f, prefix=f"{u['username']}_sub")
            if url:
                sub_urls.append(url)

        body = payload | {"main_image_url": main_url, "sub_image_urls": sub_urls}

        # Gọi listing-service
        try:
            r = requests.post(
                f"{LISTING_URL}/listings/",
                json=body,
                headers={"Authorization": f"Bearer {session.get('access_token','')}"},
                timeout=8
            )
        except requests.RequestException:
            flash("Không kết nối được Listing service.", "error")
            return render_template("post_product.html")

        if r.status_code == 201:
            flash("Đăng tin thành công! Bài đang chờ admin duyệt.", "success")
            return redirect(url_for("home"))
        else:
            msg = None
            if r.headers.get("content-type", "").startswith("application/json"):
                try:
                    msg = r.json().get("error")
                except Exception:
                    msg = None
            flash(msg or "Đăng tin thất bại.", "error")

    return render_template("post_product.html")

@app.get("/listings/<int:pid>")
def product_detail(pid):
    try:
        r = requests.get(f"{LISTING_URL}/listings/{pid}", timeout=6)
        if not r.ok or not r.headers.get("content-type","").startswith("application/json"):
            flash("Không tải được thông tin sản phẩm.", "error")
            return redirect(url_for("home"))
        item = r.json()
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")
        return redirect(url_for("home"))

    return render_template("product_detail.html", item=item)


# ---------- Admin dashboard ----------
@app.route("/admin", methods=["GET"], endpoint="admin_page")
def admin_page():
    users = []
    products = []
    transactions = []

    if is_admin_session():
        try:
            headers = {"Authorization": f"Bearer {session['access_token']}"}
            r = requests.get(f"{AUTH_URL}/auth/admin/users", headers=headers, timeout=5)
            if r.ok and r.headers.get("content-type", "").startswith("application/json"):
                users = r.json().get("data", [])
        except requests.RequestException:
            flash("Không kết nối được auth service.", "error")

    try:
        r2 = requests.get(f"{LISTING_URL}/listings/?sort=created_desc", timeout=8)
        if r2.ok and r2.headers.get("content-type", "").startswith("application/json"):
            data = r2.json()
            products = data.get("items", data if isinstance(data, list) else [])
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")

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

# ---- Admin duyệt / bỏ duyệt / xóa bài đăng ----
@app.post("/admin/approve/<int:pid>")
@app.get("/admin/approve/<int:pid>")
def approve_product(pid):
    if not is_admin_session():
        session["next_after_login"] = url_for("approve_product", pid=pid)
        return redirect(url_for("login_page"))

    try:
        r = requests.put(
            f"{LISTING_URL}/listings/{pid}/approve",
            headers={"Authorization": f"Bearer {session.get('access_token','')}"}
        )
        if r.ok:
            flash("✅ Đã duyệt bài đăng.", "success")
        else:
            msg = None
            if r.headers.get("content-type", "").startswith("application/json"):
                try:
                    msg = r.json().get("error")
                except Exception:
                    msg = None
            flash(msg or "Không duyệt được bài đăng.", "error")
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")

    return redirect(url_for("admin_page"))

@app.get("/admin/delete/<int:pid>")
def delete_product(pid):
    if not is_admin_session():
        session["next_after_login"] = url_for("delete_product", pid=pid)
        return redirect(url_for("login_page"))

    try:
        r = requests.delete(
            f"{LISTING_URL}/listings/{pid}",
            headers={"Authorization": f"Bearer {session.get('access_token','')}"}
        )
        if r.ok:
            flash("Đã xoá bài đăng.", "success")
        else:
            msg = None
            if r.headers.get("content-type", "").startswith("application/json"):
                try:
                    msg = r.json().get("error")
                except Exception:
                    msg = None
            flash(msg or "Xoá thất bại.", "error")
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")

    return redirect(url_for("admin_page"))

# ---- Quản lý user (auth-service) ----
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

# ---------- AI Price Suggest ----------

@app.post("/ai/price_suggest")
def price_suggest():
    # 1) Nhận JSON hoặc form
    if request.content_type and request.content_type.startswith("application/json"):
        raw = request.get_json(silent=True) or {}
    else:
        raw = request.form.to_dict()

    # 2) Chuẩn hóa trường & ép kiểu số
    product_type = (raw.get("product_type") or "car").strip().lower()
    name         = (raw.get("name") or "").strip()
    brand        = (raw.get("brand") or "").strip()
    province     = (raw.get("province") or "").strip()
    year         = _num(raw.get("year"))
    mileage      = _num(raw.get("mileage"))
    cap_kwh      = _num(raw.get("battery_capacity_kwh") or raw.get("battery_capacity"))
    description  = (raw.get("description") or "").strip()

    payload = {
        "product_type": product_type,
        "name": name,
        "brand": brand,
        "province": province,
        "year": int(year) if year is not None else None,
        "mileage": int(mileage) if mileage is not None else None,
        "battery_capacity_kwh": float(cap_kwh) if cap_kwh is not None else None,
        "description": description,
    }

    # 3) Gọi pricing_service với timeout kép (connect=5s, read=90s)
    try:
        r = requests.post(f"{PRICING_URL}/predict", json=payload, timeout=(5, 90))
    except requests.exceptions.ReadTimeout as e:
        app.logger.exception("pricing-service read timeout")
        return jsonify(error="pricing-service quá thời gian phản hồi", detail=str(e)), 504
    except requests.exceptions.RequestException as e:
        app.logger.exception("price_suggest failed: %s", e)
        return jsonify(error="Không kết nối được pricing-service", detail=str(e)), 502

    # 4) Trả đúng JSON/Status của pricing_service
    ct = r.headers.get("content-type", "")
    if ct.startswith("application/json"):
        try:
            return jsonify(r.json()), r.status_code
        except Exception:
            pass
    return (r.text, r.status_code, {"Content-Type": ct or "text/plain"})

@app.get("/health")
def health():
    return {"status": "ok"}, 200

@app.get("/__routes")
def __routes():
    out=[]
    for rule in app.url_map.iter_rules():
        methods=",".join(sorted(rule.methods - {"HEAD","OPTIONS"}))
        out.append({"rule": str(rule), "methods": methods})
    return {"routes": out}, 200



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
