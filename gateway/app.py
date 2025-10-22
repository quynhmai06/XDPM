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
TRANSACTIONS_URL = os.getenv("TRANSACTIONS_URL", "http://127.0.0.1:5008")
JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("GATEWAY_SECRET", "devsecret"))
JWT_ALGOS = ["HS256"]

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("GATEWAY_SECRET", "dev")

def decode_token(token: str):
    return jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS)

def is_admin_session() -> bool:
    user = session.get("user")
    return bool(user and user.get("role") == "admin")

def get_current_user():
    # Prefer session (browser flows)
    user = session.get("user")
    if user:
        return user
    # Fallback to Authorization header (API/script flows)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        try:
            return decode_token(token)
        except Exception:
            return None
    return None

# ===== Cart helpers =====
def _get_cart():
    cart = session.get('cart')
    if cart is None:
        cart = []
        session['cart'] = cart
    return cart

def _save_cart(cart):
    session['cart'] = cart

def _cart_find(cart, item_type, item_id):
    for it in cart:
        if it.get('item_type') == item_type and it.get('item_id') == item_id:
            return it
    return None

@app.route("/", endpoint="home")
def home_page():
    return render_template("index.html")

@app.route("/compare", methods=["GET"], endpoint="compare_page")
def compare_page():
    return render_template("compare.html")

# NOTE: Trang danh sách đấu giá đã được tích hợp vào trang chủ (index.html)
# Không cần trang riêng /auctions nữa
# @app.get('/auctions')
# def auctions_page():
#     return render_template('auctions.html')

# GIỮ trang chi tiết đấu giá - user click vào card ở trang chủ sẽ vào đây
@app.get('/auctions/<int:aid>')
def auction_detail_page(aid:int):
    return render_template('auction_detail.html')

@app.post('/auctions/create')
def auctions_create():
    user = get_current_user()
    if not user:
        session['next_after_login'] = url_for('auctions_page')
        return redirect(url_for('login_page'))
    # read form and post to auctions service
    item_type = request.form.get('item_type')
    item_id = request.form.get('item_id', type=int)
    starting_price = request.form.get('starting_price', type=int)
    buy_now_price = request.form.get('buy_now_price', type=int)
    ends_at_local = request.form.get('ends_at_local')  # YYYY-MM-DDTHH:mm
    ends_at = None
    try:
        # convert to UTC ISO string without timezone assumption (browser local time)
        # simple passthrough if client sends ISO full
        from datetime import datetime, timezone
        if ends_at_local and 'T' in ends_at_local:
            dt = datetime.fromisoformat(ends_at_local)
            ends_at = dt.astimezone(timezone.utc).isoformat()
    except Exception:
        ends_at = ends_at_local
    payload = {
        'item_type': item_type,
        'item_id': item_id,
        'seller_id': user.get('sub'),
        'starting_price': starting_price,
        'buy_now_price': buy_now_price,
        'ends_at': ends_at or ends_at_local
    }
    try:
        r = requests.post(f"{AUCTIONS_URL}/auctions", json=payload, timeout=5)
        if r.status_code in (200,201):
            flash('Tạo phiên đấu giá thành công!', 'success')
        else:
            flash('Tạo phiên đấu giá thất bại.', 'error')
    except requests.RequestException:
        flash('Không kết nối được auctions service.', 'error')
    return redirect(url_for('auctions_page'))

@app.route("/favorites", methods=["GET"], endpoint="favorites_page")
def favorites_page():
    user = get_current_user()
    if not user:
        session["next_after_login"] = url_for("favorites_page")
        return redirect(url_for("login_page"))
    # Fetch enriched favorites via our own API (ensures same logic)
    headers = {"Authorization": f"Bearer {session.get('access_token')}"} if session.get('access_token') else {}
    try:
        r = requests.get(f"http://localhost:8000/api/favorites", headers=headers, timeout=5)
        favs = r.json().get('data', []) if r.ok else []
    except Exception:
        favs = []
    return render_template("favorites.html", favs=favs, user=user)

@app.route("/reviews", methods=["GET"], endpoint="reviews_page")
def reviews_page():
    user = get_current_user()
    if not user:
        session["next_after_login"] = url_for("reviews_page")
        return redirect(url_for("login_page"))
    return render_template("reviews.html", user=user)

# ===== Cart & Checkout pages =====
@app.post('/cart/add')
def cart_add():
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    d = request.get_json(force=True)
    item_type = d.get('item_type')
    item_id = d.get('item_id')
    seller_id = d.get('seller_id')
    price = d.get('price', 0)
    qty = max(int(d.get('qty', 1)), 1)
    if not item_type or not item_id:
        return {"error": "missing_fields"}, 400
    cart = _get_cart()
    existing = _cart_find(cart, item_type, item_id)
    if existing:
        existing['qty'] = existing.get('qty', 1) + qty
        existing['price'] = price or existing.get('price', 0)
        existing['seller_id'] = seller_id or existing.get('seller_id')
    else:
        cart.append({
            'item_type': item_type,
            'item_id': item_id,
            'seller_id': seller_id,
            'price': price,
            'qty': qty
        })
    _save_cart(cart)
    return {"ok": True, "count": sum(i.get('qty',1) for i in cart)}

@app.post('/cart/update')
def cart_update():
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    d = request.get_json(force=True)
    item_type = d.get('item_type')
    item_id = d.get('item_id')
    qty = max(int(d.get('qty', 1)), 0)
    cart = _get_cart()
    it = _cart_find(cart, item_type, item_id)
    if not it:
        return {"error": "not_found"}, 404
    if qty == 0:
        cart.remove(it)
    else:
        it['qty'] = qty
    _save_cart(cart)
    return {"ok": True}

@app.post('/cart/remove')
def cart_remove():
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    d = request.get_json(force=True)
    item_type = d.get('item_type')
    item_id = d.get('item_id')
    cart = _get_cart()
    it = _cart_find(cart, item_type, item_id)
    if not it:
        return {"error": "not_found"}, 404
    cart.remove(it)
    _save_cart(cart)
    return {"ok": True}

def _enrich_item(it):
    item = None
    try:
        if it.get('item_type') == 'vehicle':
            ir = requests.get(f"{LISTINGS_URL}/listings/vehicles/{it.get('item_id')}", timeout=5)
            if ir.ok:
                item = ir.json()
        elif it.get('item_type') == 'battery':
            ir = requests.get(f"{LISTINGS_URL}/listings/batteries/{it.get('item_id')}", timeout=5)
            if ir.ok:
                item = ir.json()
    except requests.RequestException:
        item = None
    return item

@app.get('/cart')
def cart_page():
    user = get_current_user()
    if not user:
        session['next_after_login'] = url_for('cart_page')
        return redirect(url_for('login_page'))
    cart = _get_cart()
    enriched = []
    subtotal = 0
    for it in cart:
        info = _enrich_item(it)
        price = it.get('price') or (info.get('price') if info else 0)
        qty = it.get('qty', 1)
        line = {**it, 'item': info, 'price': price, 'line_total': price * qty}
        subtotal += line['line_total']
        enriched.append(line)
    return render_template('cart.html', items=enriched, subtotal=subtotal)

@app.get('/checkout')
def checkout_page():
    user = get_current_user()
    if not user:
        session['next_after_login'] = url_for('checkout_page')
        return redirect(url_for('login_page'))
    cart = _get_cart()
    if not cart:
        flash('Giỏ hàng trống.', 'error')
        return redirect(url_for('home'))
    enriched = []
    subtotal = 0
    for it in cart:
        info = _enrich_item(it)
        price = it.get('price') or (info.get('price') if info else 0)
        qty = it.get('qty', 1)
        line = {**it, 'item': info, 'price': price, 'line_total': price * qty}
        subtotal += line['line_total']
        enriched.append(line)
    shipping = 0
    total = subtotal + shipping
    return render_template('checkout.html', items=enriched, subtotal=subtotal, shipping=shipping, total=total)

@app.post('/checkout/place')
def checkout_place():
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    cart = _get_cart()
    if not cart:
        return {"error": "empty_cart"}, 400
    created = []
    for it in cart:
        payload = {
            'buyer_id': user['sub'],
            'seller_id': it.get('seller_id'),
            'item_type': it.get('item_type'),
            'item_id': it.get('item_id'),
            'price': it.get('price') or 0
        }
        try:
            r = requests.post(f"{ORDERS_URL}/orders", json=payload, timeout=5)
            if r.ok:
                created.append(r.json().get('id'))
        except requests.RequestException:
            pass
    # Clear cart after placing orders
    _save_cart([])
    return {"ok": True, "order_ids": created}

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

@app.get('/api/listings/vehicles/<int:id>')
def api_get_vehicle(id):
    try:
        r = requests.get(f"{LISTINGS_URL}/listings/vehicles/{id}", timeout=5)
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

@app.get('/api/listings/batteries/<int:id>')
def api_get_battery(id):
    try:
        r = requests.get(f"{LISTINGS_URL}/listings/batteries/{id}", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "listings_unavailable"}, 503

@app.get('/api/favorites')
def api_favorites_list():
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    try:
        r = requests.get(f"{FAVORITES_URL}/favorites/me", params={"user_id": user['sub']}, timeout=5)
        if not r.ok:
            return (r.json() if r.headers.get('content-type','').startswith('application/json') else {"error":"favorites_error"}, r.status_code)
        data = r.json().get('data', [])
        enriched = []
        for f in data:
            item = None
            try:
                if f.get('item_type') == 'vehicle':
                    ir = requests.get(f"{LISTINGS_URL}/listings/vehicles/{f.get('item_id')}", timeout=5)
                    if ir.ok:
                        item = ir.json()
                elif f.get('item_type') == 'battery':
                    ir = requests.get(f"{LISTINGS_URL}/listings/batteries/{f.get('item_id')}", timeout=5)
                    if ir.ok:
                        item = ir.json()
            except requests.RequestException:
                item = None
            enriched.append({
                **f,
                "item": item
            })
        return ({"data": enriched}, 200)
    except requests.RequestException:
        return {"error": "favorites_unavailable"}, 503

@app.post('/api/favorites')
def api_favorites_add():
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    d = request.get_json(force=True)
    d['user_id'] = user['sub']
    try:
        r = requests.post(f"{FAVORITES_URL}/favorites", json=d, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "favorites_unavailable"}, 503

@app.delete('/api/favorites/<int:fav_id>')
def api_favorites_delete(fav_id:int):
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    try:
        r = requests.delete(f"{FAVORITES_URL}/favorites/{fav_id}", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "favorites_unavailable"}, 503

@app.post('/api/orders')
def api_orders_create():
    user = get_current_user()
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
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    try:
        r = requests.get(f"{ORDERS_URL}/orders/history", params={"user_id": user['sub'], "role": request.args.get('role','buyer')}, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "orders_unavailable"}, 503

@app.post('/api/auctions/<int:aid>/bid')
def api_bid(aid:int):
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    d = request.get_json(force=True)
    d['bidder_id'] = user['sub']
    try:
        r = requests.post(f"{AUCTIONS_URL}/auctions/{aid}/bid", json=d, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "auctions_unavailable"}, 503

@app.get('/api/auctions/active')
def api_auctions_active():
    try:
        r = requests.get(f"{AUCTIONS_URL}/auctions/active", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "auctions_unavailable"}, 503

@app.get('/api/auctions/<int:aid>')
def api_auction_detail(aid:int):
    try:
        r = requests.get(f"{AUCTIONS_URL}/auctions/{aid}", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "auctions_unavailable"}, 503

@app.get('/api/auctions/<int:aid>/bids')
def api_auction_bids(aid:int):
    try:
        r = requests.get(f"{AUCTIONS_URL}/auctions/{aid}/bids", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "auctions_unavailable"}, 503

@app.post('/api/auctions/<int:aid>/buy-now')
def api_buy_now(aid:int):
    # Require logged-in user; on success, close auction and create order
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    try:
        ar = requests.post(f"{AUCTIONS_URL}/auctions/{aid}/buy-now", timeout=5)
    except requests.RequestException:
        return {"error": "auctions_unavailable"}, 503
    if not ar.ok:
        # bubble up auctions error
        try:
            return (ar.json(), ar.status_code)
        except Exception:
            return ({"error": "auction_buy_now_failed"}, ar.status_code)
    if ar.headers.get('content-type', '').startswith('application/json'):
        try:
            data = ar.json()
        except ValueError:
            data = {}
    else:
        data = {}
    response = {
        "ok": True,
        "auction_closed": True,
        "auction_id": data.get("auction_id", aid),
        "item_type": data.get("item_type"),
        "item_id": data.get("item_id"),
        "seller_id": data.get("seller_id"),
        "final_price": data.get("final_price"),
        "buy_now_price": data.get("buy_now_price")
    }
    return (response, 200)

@app.post('/api/reviews')
def api_reviews_create():
    user = get_current_user()
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

@app.get('/api/reviews/by-reviewer/<int:reviewer_id>')
def api_reviews_by_reviewer(reviewer_id:int):
    try:
        r = requests.get(f"{REVIEWS_URL}/reviews/by-reviewer/{reviewer_id}", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "reviews_unavailable"}, 503

@app.get('/api/reviews/pending')
def api_reviews_pending():
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    try:
        r = requests.get(f"{REVIEWS_URL}/reviews/pending/{user['sub']}", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "reviews_unavailable"}, 503

@app.patch('/api/reviews/<int:review_id>')
def api_reviews_update(review_id:int):
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    d = request.get_json(force=True)
    d['requester_id'] = user['sub']
    try:
        r = requests.patch(f"{REVIEWS_URL}/reviews/{review_id}", json=d, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "reviews_unavailable"}, 503

@app.delete('/api/reviews/<int:review_id>')
def api_reviews_delete(review_id:int):
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    try:
        r = requests.delete(f"{REVIEWS_URL}/reviews/{review_id}?requester_id={user['sub']}", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "reviews_unavailable"}, 503

@app.post('/api/reviews/<int:review_id>/helpful')
def api_reviews_helpful(review_id:int):
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    try:
        r = requests.post(f"{REVIEWS_URL}/reviews/{review_id}/helpful", json={"user_id": user['sub']}, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "reviews_unavailable"}, 503

@app.post('/api/reviews/<int:review_id>/report')
def api_reviews_report(review_id:int):
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    d = request.get_json(force=True)
    d['reporter_id'] = user['sub']
    try:
        r = requests.post(f"{REVIEWS_URL}/reviews/{review_id}/report", json=d, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "reviews_unavailable"}, 503


# ===== Transaction History Routes =====
@app.get('/transactions')
def transactions_page():
    """Trang lịch sử giao dịch"""
    user = get_current_user()
    if not user:
        session['next_after_login'] = url_for('transactions_page')
        return redirect(url_for('login_page'))
    return render_template('transactions.html', user=user)


@app.get('/api/transactions/user/<int:user_id>')
def api_get_user_transactions(user_id: int):
    """API lấy giao dịch của user (mua hàng + bán hàng)"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    # Security: user chỉ xem được GD của mình, trừ admin
    if user.get('sub') != user_id and user.get('role') != 'admin':
        return {"error": "forbidden"}, 403
    
    # Forward query params
    params = dict(request.args)
    try:
        r = requests.get(f"{TRANSACTIONS_URL}/transactions/user/{user_id}", params=params, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "transactions_unavailable"}, 503


@app.get('/api/transactions/wallet/<int:user_id>')
def api_get_wallet_transactions(user_id: int):
    """API lấy lịch sử ví điện tử"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    if user.get('sub') != user_id and user.get('role') != 'admin':
        return {"error": "forbidden"}, 403
    
    params = dict(request.args)
    try:
        r = requests.get(f"{TRANSACTIONS_URL}/transactions/wallet/{user_id}", params=params, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "transactions_unavailable"}, 503


@app.get('/api/transactions/<int:transaction_id>')
def api_get_transaction_detail(transaction_id: int):
    """API lấy chi tiết giao dịch + timeline"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        r = requests.get(f"{TRANSACTIONS_URL}/transactions/{transaction_id}", timeout=5)
        if r.ok:
            data = r.json()
            # Security check: user phải là người tham gia GD
            if user.get('role') != 'admin':
                if data.get('user_id') != user.get('sub') and data.get('partner_id') != user.get('sub'):
                    return {"error": "forbidden"}, 403
            return (data, 200)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "transactions_unavailable"}, 503


@app.get('/api/transactions/admin/all')
def api_admin_get_all_transactions():
    """API admin xem tất cả giao dịch"""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        return {"error": "forbidden"}, 403
    
    params = dict(request.args)
    try:
        r = requests.get(f"{TRANSACTIONS_URL}/transactions/admin/all", params=params, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "transactions_unavailable"}, 503

