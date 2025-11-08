# gateway/app.py 
from flask import Flask, render_template, redirect, url_for, request, session, flash, Response, jsonify
import os, requests, jwt, time, json, re
from functools import wraps
from werkzeug.utils import secure_filename

# ===================== Config =====================
AUTH_URL     = os.getenv("AUTH_URL",     "http://auth_service:5001")
ADMIN_URL    = os.getenv("ADMIN_URL",    "http://admin_service:5003")
LISTING_URL  = os.getenv("LISTING_URL",  "http://listing_service:5002")
SEARCH_URL   = os.getenv("SEARCH_URL",   "http://search_service:5003")
PRICING_URL  = os.getenv("PRICING_URL",  "http://pricing_service:5003")

JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
JWT_ALGOS  = ["HS256"]

app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")
app.secret_key = os.getenv("GATEWAY_SECRET", "dev")
app.config.update(SESSION_COOKIE_SAMESITE="Lax")

# uploads: gateway lưu ảnh, gửi URL cho listing-service
UPLOAD_DIR = os.path.join(app.static_folder, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp"}

# ===================== Helpers =====================
def _num(x):
    if x is None: 
        return None
    m = re.search(r"\d+(?:\.\d+)?", str(x))
    return float(m.group(0)) if m else None

def save_image(file_storage, prefix="img"):
    if not file_storage or file_storage.filename == "":
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTS:
        return None
    fname = f"{prefix}_{int(time.time()*1000)}_{secure_filename(file_storage.filename)}"
    path = os.path.join(UPLOAD_DIR, fname)
    file_storage.save(path)
    return f"/static/uploads/{fname}"  # public URL served by gateway

def decode_token(token: str):
    # bỏ verify_sub để tránh lỗi nếu sub không phải string
    return jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS, options={"verify_sub": False})

def is_admin_session() -> bool:
    token = session.get("access_token")
    if not token:
        return False
    try:
        payload = decode_token(token)
        return str(payload.get("role", "")).lower() == "admin"
    except Exception:
        return False

def login_required(next_endpoint_name="login_page"):
    def _wrap(f):
        @wraps(f)
        def inner(*args, **kwargs):
            token = session.get("access_token")
            if not token:
                # lưu lại route để quay lại sau khi login
                session["next_after_login"] = url_for(request.endpoint, **(request.view_args or {}))
                return redirect(url_for(next_endpoint_name))
            return f(*args, **kwargs)
        return inner
    return _wrap

def _update_display_name_from_payload(obj):
    """Đồng bộ display name vào session sau khi GET/PUT/POST profile ok."""
    if not isinstance(obj, dict):
        return
    prof = obj.get("profile") if "profile" in obj else obj
    if isinstance(prof, dict):
        dn = prof.get("full_name") or prof.get("display_name")
        if dn:
            session["display_name"] = dn
            u = session.get("user") or {}
            u["full_name"] = dn
            session["user"] = u
            session.modified = True

# ===================== Basic/Health =====================
@app.get("/health")
def health():
    return {"status": "ok"}, 200

@app.get("/__routes")
def __routes():
    out=[]
    for rule in app.url_map.iter_rules():
        methods=",".join(sorted(rule.methods - {"HEAD","OPTIONS"}))
        out.append({"rule": str(rule), "methods": methods, "endpoint": rule.endpoint})
    return {"routes": out}, 200

# ===================== Home =====================
@app.route("/", endpoint="home")
def home():
    """Homepage with search and listings"""
    # Check if we have any search parameters
    has_search_params = any([
        request.args.get("q"),
        request.args.get("brand"),
        request.args.get("province"),
        request.args.get("item_type"),
        request.args.get("min_price"),
        request.args.get("max_price"),
        request.args.get("year_from"),
        request.args.get("year_to"),
        request.args.get("mileage_max"),
        request.args.get("battery_capacity_min"),
        request.args.get("battery_capacity_max"),
        request.args.get("sort"),
    ])
    
    if has_search_params:
        # User is searching - call search service
        params = {}
        
        # Build search parameters
        for key in ["q", "brand", "province", "item_type", "min_price", "max_price",
                    "year_from", "year_to", "mileage_min", "mileage_max",
                    "battery_capacity", "battery_capacity_min", "battery_capacity_max", "sort"]:
            val = request.args.get(key, "").strip()
            if val:
                params[key] = val
        
        # Always filter approved items
        params["approved"] = "1"
        
        # Pagination
        page = request.args.get("page", "1")
        per_page = request.args.get("per_page", "20")
        params["page"] = page
        params["per_page"] = per_page
        
        # Call search service
        try:
            resp = requests.get(f"{SEARCH_URL}/search/listings", params=params, timeout=10)
            if resp.ok:
                data = resp.json()
                search_results = data.get("items", [])
                total = data.get("total", 0)
                pages = data.get("pages", 1)
                current_page = data.get("page", 1)
                
                return render_template(
                    "index.html",
                    cars=[],  # Don't show default cars when searching
                    batts=[],  # Don't show default batts when searching
                    search_results=search_results,
                    total=total,
                    pages=pages,
                    current_page=current_page,
                    query_params=params,
                    is_search=True
                )
        except requests.RequestException:
            pass
    
    # Default homepage - show featured cars and batteries
    def fetch(params):
        try:
            r = requests.get(f"{LISTING_URL}/listings/", params=params, timeout=6)
            if r.ok and r.headers.get("content-type","").startswith("application/json"):
                return r.json().get("items", [])
        except requests.RequestException:
            pass
        return []

    cars = fetch({
        "approved": "1",
        "item_type": "vehicle",
        "sort": "created_desc",
        "per_page": 12,
    })

    batts = fetch({
        "approved": "1",
        "item_type": "battery",
        "sort": "created_desc",
        "per_page": 12,
    })

    return render_template("index.html", cars=cars, batts=batts, is_search=False)



# ===================== Auth =====================
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
                              json={"username": username, "password": password}, timeout=8)
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
            return redirect(next_url or (url_for("admin_page") if is_admin_session() else url_for("home")))
        flash("Đăng nhập thất bại.", "error")
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
            r = requests.post(f"{AUTH_URL}/auth/register",
                              json={"username": username, "email": email, "password": password},
                              timeout=10)
        except requests.RequestException:
            flash("Không kết nối được Auth service.", "error")
            return render_template("register.html")
        if r.status_code in (200, 201):
            flash("Đăng ký thành công! Vui lòng chờ admin duyệt.", "success")
            return redirect(url_for("login_page"))
        msg = None
        if r.headers.get("content-type","").startswith("application/json"):
            msg = (r.json() or {}).get("error")
        flash(msg or "Đăng ký thất bại.", "error")
    return render_template("register.html")

@app.get("/logout", endpoint="logout_page")
def logout_page():
    was_admin = is_admin_session()
    session.clear()
    flash("Đã đăng xuất!", "success")
    return redirect(url_for("admin_page") if was_admin else url_for("home"))

# ===================== Profile proxy (auth-service) =====================
@app.route("/auth/me")
def proxy_me():
    token = session.get("access_token")
    if not token:
        return Response("Unauthorized", status=401)
    try:
        r = requests.get(f"{AUTH_URL}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=8)
        ctype = r.headers.get("content-type") or "application/json"
        return Response(r.content, status=r.status_code, content_type=ctype)
    except requests.RequestException:
        return Response("Auth service unreachable", status=502)

@app.route("/auth/profile", methods=["GET", "PUT", "POST"])
def proxy_profile():
    token = session.get("access_token")
    if not token:
        return Response("Unauthorized", status=401)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        if request.method == "GET":
            r = requests.get(f"{AUTH_URL}/auth/profile", headers=headers, timeout=10)
            if r.ok and (r.headers.get("content-type","").startswith("application/json")):
                try: _update_display_name_from_payload(r.json())
                except Exception: pass
        elif request.method == "PUT":
            r = requests.put(f"{AUTH_URL}/auth/profile",
                             headers={**headers, "Content-Type": "application/json"},
                             json=request.json, timeout=12)
            if r.ok and (r.headers.get("content-type","").startswith("application/json")):
                try: _update_display_name_from_payload(r.json())
                except Exception: pass
        else:  # POST multipart (upload avatar)
            files = {name: (fs.filename, fs.read(), fs.mimetype or "application/octet-stream")
                     for name, fs in request.files.items()}
            r = requests.post(f"{AUTH_URL}/auth/profile", headers=headers,
                              files=files, data=request.form, timeout=20)
            if r.ok and (r.headers.get("content-type","").startswith("application/json")):
                try: _update_display_name_from_payload(r.json())
                except Exception: pass
        ctype = r.headers.get("content-type") or "application/json"
        return Response(r.content, status=r.status_code, content_type=ctype)
    except requests.RequestException:
        return Response("Auth service unreachable", status=502)

@app.get("/auth/avatar/<path:name>")
def proxy_avatar(name):
    headers = {}
    if session.get("access_token"):
        headers["Authorization"] = f"Bearer {session['access_token']}"
    try:
        r = requests.get(f"{AUTH_URL}/auth/avatar/{name}", headers=headers, timeout=12, stream=True)
    except requests.RequestException:
        return Response("Auth service unreachable", status=502)
    ctype = r.headers.get("content-type", "image/jpeg")
    return Response(r.content, status=r.status_code, content_type=ctype)

# ===================== Listings (Member) =====================
@app.route("/listings/new", methods=["GET", "POST"], endpoint="add_listing")
@login_required()
def add_listing():
    u = session.get("user") or {}
    if request.method == "POST":
        payload = {
            "product_type": (request.form.get("product_type") or "car").strip(),
            "name": (request.form.get("name") or "").strip(),
            "description": (request.form.get("description") or "").strip(),
            "price": int(_num(request.form.get("price")) or 0),
            "brand": (request.form.get("brand") or "").strip(),
            "province": (request.form.get("province") or "").strip(),
            "year": int(_num(request.form.get("year")) or 0),
            "mileage": int(_num(request.form.get("mileage")) or 0),
            "battery_capacity": (request.form.get("battery_capacity") or "").strip(),
        }
        if not payload["name"] or payload["price"] <= 0:
            flash("Nhập các thông tin bắt buộc!", "error")
            return render_template("post_product.html")

        # upload ảnh
        main_url = save_image(request.files.get("main_image"), prefix=f"{u.get('username','user')}_main")
        sub_urls = []
        for f in request.files.getlist("sub_images"):
            url = save_image(f, prefix=f"{u.get('username','user')}_sub")
            if url:
                sub_urls.append(url)
        pt = payload.get("product_type", "car").lower()
        item_type = "vehicle" if pt == "car" else "battery"

        body = {
            "item_type": item_type,                     
            "name": payload["name"],
            "description": payload["description"],
            "price": payload["price"],
            "brand": payload["brand"],
            "province": payload["province"],
            "year": payload["year"],
            "mileage": payload["mileage"],
            "battery_capacity": payload["battery_capacity"],
            "main_image_url": main_url,
            "sub_image_urls": sub_urls,
    }

        try:
            r = requests.post(
                f"{LISTING_URL}/listings/",
                json=body,
                headers={"Authorization": f"Bearer {session.get('access_token','')}"},
                timeout=10
            )
        except requests.RequestException:
            flash("Không kết nối được Listing service.", "error")
            return render_template("post_product.html")
        if r.status_code == 201:
            flash("Đăng tin thành công! Bài đang chờ admin duyệt.", "success")
            return redirect(url_for("home"))

        if r.status_code == 403:
            msg = None
            try:
                if r.headers.get("content-type","").startswith("application/json"):
                    msg = (r.json() or {}).get("error")
            except Exception:
                pass
            flash(msg or "Tài khoản của bạn đang bị hạn chế đăng tin (spam).", "error")
            return render_template("post_product.html"), 403

        ct = r.headers.get("content-type", "")
        msg = None
        if ct.startswith("application/json"):
            try:
                msg = r.json().get("error")
            except Exception:
                pass
        flash(f"Đăng tin thất bại (HTTP {r.status_code}). {msg or (r.text or '')[:200]}", "error")
        return render_template("post_product.html"), r.status_code


    return render_template("post_product.html")



@app.get("/listings/<int:pid>")
def product_detail(pid):
    try:
        r = requests.get(f"{LISTING_URL}/listings/{pid}", timeout=8)
        if not r.ok or not r.headers.get("content-type","").startswith("application/json"):
            flash("Không tải được thông tin sản phẩm.", "error")
            return redirect(url_for("home"))
        item = r.json()
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")
        return redirect(url_for("home"))
    return render_template("product_detail.html", item=item)

# ===================== Admin (duyệt/xoá bài, duyệt user) =====================
@app.route("/admin", methods=["GET"], endpoint="admin_page")
def admin_page():
    users, products, transactions = [], [], []

    # --- tham số lọc luôn có giá trị mặc định ---
    cur_status   = (request.args.get("status") or "").strip()     # '', pending, approved, spam, rejected
    cur_verified = (request.args.get("verified") or "").strip()   # '', '1', '0'

    # ---- USERS (chỉ khi là admin) ----
    if is_admin_session():
        headers = {"Authorization": f"Bearer {session['access_token']}"}
        for url in (f"{ADMIN_URL}/admin/users",
                    f"{AUTH_URL}/auth/admin/users",
                    f"{AUTH_URL}/auth/users"):
            try:
                r = requests.get(url, headers=headers, timeout=8)
                if r.ok and r.headers.get("content-type","").startswith("application/json"):
                    data = r.json()
                    raw = data.get("data", data if isinstance(data, list) else [])
                    users = [u for u in raw if not (u.get("is_admin") or str(u.get("role","")).lower()=="admin")]
                    break
            except requests.RequestException:
                pass

    # ---- PRODUCTS (lọc theo trạng thái/kiểm định) ----
    url = f"{LISTING_URL}/listings/?sort=created_desc"
    if cur_status in {"pending", "approved", "rejected", "spam"}:
        url += f"&status={cur_status}"
    if cur_verified in {"0", "1"}:
        url += f"&verified={'true' if cur_verified=='1' else 'false'}"

    try:
        r2 = requests.get(url, timeout=8)
        if r2.ok and r2.headers.get("content-type","").startswith("application/json"):
            data = r2.json()
            products = data.get("items", data if isinstance(data, list) else [])
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")

    return render_template(
        "admin.html",
        users=users, products=products, transactions=transactions,
        is_admin=is_admin_session(),
        cur_status=cur_status, cur_verified=cur_verified
    )



@app.post("/admin/login", endpoint="admin_login")
def admin_login():
    username = request.form.get("username","").strip()
    password = request.form.get("password","")
    if not username or not password:
        flash("Vui lòng nhập đầy đủ thông tin.", "error")
        return redirect(url_for("admin_page"))
    try:
        r = requests.post(f"{AUTH_URL}/auth/login", json={"username": username, "password": password}, timeout=8)
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
    try:
        payload = decode_token(token)
    except Exception:
        flash("Token không hợp lệ.", "error")
        return redirect(url_for("admin_page"))
    if str(payload.get("role","")).lower() != "admin":
        flash("Tài khoản không phải admin.", "error")
        return redirect(url_for("admin_page"))
    session["access_token"] = token
    session["user"] = {"username": payload.get("username"), "role": payload.get("role")}
    flash("Đăng nhập admin thành công!", "success")
    return redirect(url_for("admin_page"))

@app.get("/admin/logout", endpoint="admin_logout")
def admin_logout():
    session.clear()
    flash("Đã đăng xuất khỏi Admin!", "success")
    return redirect(url_for("admin_page"))

# --- DUYỆT ---
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
            try:
                if r.headers.get("content-type","").startswith("application/json"):
                    msg = (r.json() or {}).get("error")
            except Exception:
                pass
            flash(msg or f"Không duyệt được (HTTP {r.status_code}).", "error")
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")
    return redirect(url_for("admin_page"))

# --- TỪ CHỐI ---
@app.post("/admin/reject/<int:pid>")
def reject_product(pid):
    if not is_admin_session():
        session["next_after_login"] = url_for("reject_product", pid=pid)
        return redirect(url_for("login_page"))
    note = request.form.get("note")
    requests.put(
        f"{LISTING_URL}/listings/{pid}/reject",
        json={"note": note},
        headers={"Authorization": f"Bearer {session.get('access_token','')}"}
    )
    return redirect(url_for("admin_page"))


@app.post("/admin/mark_spam/<int:pid>")
@app.get("/admin/mark_spam/<int:pid>")
def mark_spam(pid):
    if not is_admin_session():
        session["next_after_login"] = url_for("mark_spam", pid=pid)
        return redirect(url_for("login_page"))
    note = request.values.get("note")  
    try:
        r = requests.put(
            f"{LISTING_URL}/listings/{pid}/mark_spam",
            json={"note": note} if note else None,
            headers={"Authorization": f"Bearer {session.get('access_token','')}"}
        )
        if r.ok:
            flash("🚫 Đã gắn spam & chặn user đăng bài mới.", "success")
        else:
            msg = None
            try:
                if r.headers.get("content-type","").startswith("application/json"):
                    msg = (r.json() or {}).get("error")
            except Exception:
                pass
            flash(msg or f"Đánh dấu spam thất bại (HTTP {r.status_code}).", "error")
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")
    return redirect(url_for("admin_page"))

@app.post("/admin/unspam/<int:pid>")
@app.get("/admin/unspam/<int:pid>")
def unspam(pid):
    if not is_admin_session():
        session["next_after_login"] = url_for("unspam", pid=pid)
        return redirect(url_for("login_page"))
    try:
        r = requests.put(
            f"{LISTING_URL}/listings/{pid}/unspam",
            headers={"Authorization": f"Bearer {session.get('access_token','')}"}
        )
        flash("✅ Đã bỏ spam (mở khoá nếu không còn bài spam).", "success" if r.ok else "error")
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")
    return redirect(url_for("admin_page"))

@app.post("/admin/verify/<int:pid>")
def verify(pid):
    if not is_admin_session():
        session["next_after_login"] = url_for("verify", pid=pid)
        return redirect(url_for("login_page"))
    requests.put(f"{LISTING_URL}/listings/{pid}/verify",
                 headers={"Authorization": f"Bearer {session.get('access_token','')}"})
    return redirect(url_for("admin_page"))

@app.post("/admin/unverify/<int:pid>")
def unverify(pid):
    if not is_admin_session():
        session["next_after_login"] = url_for("unverify", pid=pid)
        return redirect(url_for("login_page"))
    requests.put(f"{LISTING_URL}/listings/{pid}/unverify",
                 headers={"Authorization": f"Bearer {session.get('access_token','')}"})
    return redirect(url_for("admin_page"))


@app.get("/admin/delete/<int:pid>")
def delete_product(pid):
    if not is_admin_session():
        session["next_after_login"] = url_for("delete_product", pid=pid)
        return redirect(url_for("login_page"))
    try:
        r = requests.delete(f"{LISTING_URL}/listings/{pid}",
                            headers={"Authorization": f"Bearer {session.get('access_token','')}"})
        flash("Đã xoá bài đăng." if r.ok else "Xoá thất bại.", "success" if r.ok else "error")
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")
    return redirect(url_for("admin_page"))


def _try_patch(urls_with_payload, headers, timeout=8):
    last_err = "No targets"
    for url, payload in urls_with_payload:
        try:
            r = requests.patch(url, json=payload, headers=headers, timeout=timeout)
            if r.ok:
                return True, r
            last_err = f"{url} -> HTTP {r.status_code} {r.text[:200]}"
        except requests.RequestException as e:
            last_err = f"{url} -> {e}"
    return False, last_err

@app.route("/admin/approve_user/<int:user_id>", methods=["POST","GET"])
def approve_user(user_id):
    if not is_admin_session():
        session["next_after_login"] = url_for("approve_user", user_id=user_id)
        return redirect(url_for("login_page"))

    headers = {"Authorization": f"Bearer {session['access_token']}",
               "Content-Type": "application/json"}

    targets = [
        (f"{ADMIN_URL}/admin/users/{user_id}/status", {"status": "approved"}),
        (f"{AUTH_URL}/auth/admin/users/{user_id}/status", {"status": "approved"}),
        (f"{AUTH_URL}/auth/users/{user_id}/status", {"status": "approved"}),
        (f"{AUTH_URL}/auth/admin/users/{user_id}", {"approved": True}),
    ]
    ok, res = _try_patch(targets, headers)
    if ok:
        flash("✅ Đã duyệt tài khoản.", "success")
    else:
        flash(f"Không duyệt được: {res}", "error")
    return redirect(url_for("admin_page"))

@app.route("/admin/delete_user/<int:user_id>", methods=["POST","GET"])
def delete_user(user_id):
    if not is_admin_session():
        session["next_after_login"] = url_for("delete_user", user_id=user_id)
        return redirect(url_for("login_page"))

    headers = {"Authorization": f"Bearer {session['access_token']}",
               "Content-Type": "application/json"}
    targets = [
        (f"{ADMIN_URL}/admin/users/{user_id}/status", {"status": "locked"}),
        (f"{AUTH_URL}/auth/admin/users/{user_id}/status", {"status": "locked"}),
        (f"{AUTH_URL}/auth/users/{user_id}/status", {"status": "locked"}),
        (f"{AUTH_URL}/auth/admin/users/{user_id}", {"locked": True}),
    ]
    ok, res = _try_patch(targets, headers)
    if ok:
        flash("🔒 Đã khóa tài khoản.", "success")
    else:
        flash(f"Không khóa được: {res}", "error")
    return redirect(url_for("admin_page"))

 

# ===================== AI price suggest =====================
@app.post("/ai/price_suggest")
def price_suggest():
    raw = request.get_json(silent=True) or request.form.to_dict() or {}
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
    try:
        r = requests.post(f"{PRICING_URL}/predict", json=payload, timeout=(5, 90))
    except requests.exceptions.ReadTimeout as e:
        return jsonify(error="pricing-service quá thời gian phản hồi", detail=str(e)), 504
    except requests.exceptions.RequestException as e:
        return jsonify(error="Không kết nối được pricing-service", detail=str(e)), 502

    ct = r.headers.get("content-type", "")
    if ct.startswith("application/json"):
        try:
            return jsonify(r.json()), r.status_code
        except Exception:
            pass
    return (r.text, r.status_code, {"Content-Type": ct or "text/plain"})

# ===================== Profile page (UI) =====================
@app.get("/profile", endpoint="profile")
def profile_page():
    return render_template("profile.html")

@app.route("/policy", methods=["GET"], endpoint="policy_page")
def policy_page():
    return render_template("policy.html")


_AI_PRICE_CACHE = {}  
_AI_PRICE_TTL_S = 300  

def _ai_cache_get(key):
    now = __import__("time").time()
    v = _AI_PRICE_CACHE.get(key)
    if not v:
        return None
    exp, data = v
    if now > exp:
        _AI_PRICE_CACHE.pop(key, None)
        return None
    return data

def _ai_cache_set(key, data, ttl=_AI_PRICE_TTL_S):
    now = __import__("time").time()
    _AI_PRICE_CACHE[key] = (now + ttl, data)

def _ai_hash_payload(payload: dict) -> str:
    m = __import__("hashlib").sha256()
    m.update(__import__("json").dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return m.hexdigest()

def _ai_num(x):
    try:
        return _num(x) 
    except Exception:
        import re
        if x is None:
            return None
        m = re.search(r"\d+(?:\.\d+)?", str(x))
        return float(m.group(0)) if m else None

def _ai_build_predict_payload(raw: dict) -> dict:
    pt = (raw.get("product_type") or raw.get("item_type") or "car").strip().lower()
    name = (raw.get("name") or "").strip()
    brand = (raw.get("brand") or "").strip()
    province = (raw.get("province") or "").strip()
    year = _ai_num(raw.get("year"))
    mileage = _ai_num(raw.get("mileage"))
    cap_kwh = _ai_num(raw.get("battery_capacity_kwh") or raw.get("battery_capacity"))
    description = (raw.get("description") or "").strip()
    return {
        "product_type": pt,
        "name": name,
        "brand": brand,
        "province": province,
        "year": int(year) if year is not None else None,
        "mileage": int(mileage) if mileage is not None else None,
        "battery_capacity_kwh": float(cap_kwh) if cap_kwh is not None else None,
        "description": description,
    }

def _ai_safe_jsonify(obj, status=200):
    from flask import jsonify
    return jsonify(obj), status

@app.post("/ai/price_suggest_v2")
def ai_price_suggest_v2():
    import os, requests, json
    if (getattr(request, "content_type", "") or "").startswith("application/json"):
        raw = request.get_json(silent=True) or {}
    else:
        raw = request.form.to_dict()

    payload = _ai_build_predict_payload(raw)
    cache_key = _ai_hash_payload(payload)
    cached = _ai_cache_get(cache_key)
    if cached is not None:
        return _ai_safe_jsonify({"cached": True, "data": cached})

    PRICING_URL = os.getenv("PRICING_URL", "http://pricing_service:5003")
    try:
        r = requests.post(f"{PRICING_URL}/predict", json=payload, timeout=(5, 90))
    except requests.exceptions.ReadTimeout as e:
        app.logger.exception("pricing-service read timeout (v2)")
        return _ai_safe_jsonify({"error": "pricing-service quá thời gian phản hồi", "detail": str(e)}, 504)
    except requests.exceptions.RequestException as e:
        app.logger.exception("price_suggest_v2 failed: %s", e)
        return _ai_safe_jsonify({"error": "Không kết nối được pricing-service", "detail": str(e)}, 502)

    ct = (r.headers.get("content-type") or "")
    if ct.startswith("application/json"):
        try:
            data = r.json()
            _ai_cache_set(cache_key, data)
            return _ai_safe_jsonify({"cached": False, "data": data}, r.status_code)
        except Exception:
            pass
    try:
        _ai_cache_set(cache_key, {"text": r.text, "content_type": ct})
    except Exception:
        pass
    return (r.text, r.status_code, {"Content-Type": ct or "text/plain"})


@app.get("/ai/estimate_from_listing/<int:pid>")
def ai_estimate_from_listing(pid: int):
    import os, requests
    LISTING_URL = os.getenv("LISTING_URL", "http://listing_service:5002")
    PRICING_URL = os.getenv("PRICING_URL", "http://pricing_service:5003")

    headers = {}
    tok = session.get("access_token")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    try:
        r = requests.get(f"{LISTING_URL}/listings/{pid}", headers=headers, timeout=8)
        if not r.ok or not (r.headers.get("content-type","").startswith("application/json")):
            return _ai_safe_jsonify({"error": "Không tải được thông tin sản phẩm.", "status": r.status_code}, 502)
        item = r.json()
    except requests.RequestException as e:
        return _ai_safe_jsonify({"error": "Không kết nối được listing-service", "detail": str(e)}, 502)

    raw = {
        "product_type": item.get("item_type") or item.get("product_type") or "car",
        "name": item.get("name"),
        "brand": item.get("brand"),
        "province": item.get("province"),
        "year": item.get("year"),
        "mileage": item.get("mileage"),
        "battery_capacity_kwh": item.get("battery_capacity_kwh") or item.get("battery_capacity"),
        "description": item.get("description"),
    }
    payload = _ai_build_predict_payload(raw)

    cache_key = "id:" + str(pid) + ":" + _ai_hash_payload(payload)
    cached = _ai_cache_get(cache_key)
    if cached is not None:
        return _ai_safe_jsonify({"cached": True, "listing": item, "data": cached})

    try:
        r2 = requests.post(f"{PRICING_URL}/predict", json=payload, timeout=(5, 90))
    except requests.exceptions.ReadTimeout as e:
        app.logger.exception("pricing-service read timeout (from_listing)")
        return _ai_safe_jsonify({"error": "pricing-service quá thời gian phản hồi", "detail": str(e)}, 504)
    except requests.exceptions.RequestException as e:
        app.logger.exception("estimate_from_listing failed: %s", e)
        return _ai_safe_jsonify({"error": "Không kết nối được pricing-service", "detail": str(e)}, 502)

    ct2 = (r2.headers.get("content-type") or "")
    if ct2.startswith("application/json"):
        try:
            data = r2.json()
            _ai_cache_set(cache_key, data)
            return _ai_safe_jsonify({"cached": False, "listing": item, "data": data}, r2.status_code)
        except Exception:
            pass
    return (r2.text, r2.status_code, {"Content-Type": ct2 or "text/plain"})

@app.post("/ai/bulk_price_suggest")
def ai_bulk_price_suggest():
    import requests, os
    PRICING_URL = os.getenv("PRICING_URL", "http://pricing_service:5003")

    payloads = []
    if (getattr(request, "content_type", "") or "").startswith("application/json"):
        data = request.get_json(silent=True) or {}
        payloads = data.get("items") or []
    else:
        import json as _json
        try:
            payloads = _json.loads(request.form.get("items") or "[]")
        except Exception:
            payloads = []

    if not isinstance(payloads, list) or not payloads:
        return _ai_safe_jsonify({"error": "Thiếu danh sách items"}, 400)

    results = []
    for raw in payloads:
        pl = _ai_build_predict_payload(raw or {})
        key = _ai_hash_payload(pl)
        cached = _ai_cache_get(key)
        if cached is not None:
            results.append({"input": pl, "cached": True, "data": cached})
            continue
        try:
            r = requests.post(f"{PRICING_URL}/predict", json=pl, timeout=(5, 90))
            if (r.headers.get("content-type") or "").startswith("application/json"):
                data = r.json()
                _ai_cache_set(key, data)
                results.append({"input": pl, "cached": False, "data": data, "status": r.status_code})
            else:
                results.append({"input": pl, "cached": False, "text": r.text, "content_type": r.headers.get("content-type"), "status": r.status_code})
        except requests.RequestException as e:
            results.append({"input": pl, "error": str(e)})

    return _ai_safe_jsonify({"items": results}, 200)

@app.get("/ai/upstream_status")
def ai_upstream_status():
    import os, requests
    urls = {
        "auth": os.getenv("AUTH_URL", "http://auth_service:5001"),
        "listing": os.getenv("LISTING_URL", "http://listing_service:5002"),
        "pricing": os.getenv("PRICING_URL", "http://pricing_service:5003"),
    }
    out = {}
    for name, base in urls.items():
        try:
            # ưu tiên endpoint health; fallback GET /
            for path in ("/health", "/"):
                try_url = base.rstrip("/") + path
                r = requests.get(try_url, timeout=4)
                out[name] = {
                    "url": try_url,
                    "ok": r.ok,
                    "status": r.status_code,
                    "content_type": r.headers.get("content-type"),
                }
                break
            if name not in out:
                out[name] = {"url": base, "ok": False, "status": None}
        except requests.RequestException as e:
            out[name] = {"url": base, "ok": False, "error": str(e)}
    return _ai_safe_jsonify(out, 200)

@app.post("/ai/normalize_fields")
def ai_normalize_fields():
    if (getattr(request, "content_type", "") or "").startswith("application/json"):
        raw = request.get_json(silent=True) or {}
    else:
        raw = request.form.to_dict()
    return _ai_safe_jsonify(_ai_build_predict_payload(raw), 200)

@app.get("/ai/upstream_status_v2")
def ai_upstream_status_v2():
    import os, requests
    checks = {
        "auth": os.getenv("AUTH_URL", "http://auth_service:5001"),
        "listing": os.getenv("LISTING_URL", "http://listing_service:5002"),
        "pricing": os.getenv("PRICING_URL", "http://pricing_service:5003"),
    }
    out = {}
    for name, base in checks.items():
        base = base.rstrip("/")
        tried = []
        for path in ("/health", "/"):
            url = base + path
            tried.append(url)
            try:
                r = requests.get(url, timeout=4)
                out[name] = {
                    "url": url,
                    "ok": r.ok,
                    "status": r.status_code,
                    "content_type": r.headers.get("content-type"),
                }
                if r.ok:
                    break
            except requests.RequestException as e:
                out[name] = {"url": url, "ok": False, "error": str(e)}
        out[name]["tried"] = tried
    return (out, 200)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
