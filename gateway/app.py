from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
import os, requests, jwt, time, re
from werkzeug.utils import secure_filename


def _num(value):
    if value is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None

AUTH_URL = os.getenv("AUTH_URL", "http://auth_service:5001")
LISTING_URL = os.getenv("LISTING_URL", "http://listing_service:5002")
PRICING_URL = os.getenv("PRICING_URL", "http://pricing_service:5003")
# Use container ports for in-network calls
ADMIN_URL = os.getenv("ADMIN_URL", "http://admin_service:5002")
SEARCH_URL = os.getenv("SEARCH_URL", "http://search_service:5010")
FAVORITES_URL = os.getenv("FAVORITES_URL", "http://favorites_service:5004")
ORDERS_URL = os.getenv("ORDERS_URL", "http://orders_service:5005")
REVIEWS_URL = os.getenv("REVIEWS_URL", "http://reviews_service:5007")
TRANSACTIONS_URL = os.getenv("TRANSACTIONS_URL", "http://transactions_service:5008")
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payment_service:5003")
JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("GATEWAY_SECRET", "devsecret"))
JWT_ALGOS = ["HS256"]

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("GATEWAY_SECRET", "dev")

def decode_token(token: str):
    return jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS, options={"verify_sub": False})

def is_admin_session() -> bool:
    # Admin session is tracked separately to avoid overriding normal user session
    auser = session.get("admin_user")
    return bool(auser and auser.get("role") == "admin")

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


UPLOAD_DIR = os.path.join(app.static_folder, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def save_image(file_storage, prefix="img"):
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None
    filename = f"{prefix}_{int(time.time() * 1000)}_{secure_filename(file_storage.filename)}"
    path = os.path.join(UPLOAD_DIR, filename)
    file_storage.save(path)
    return f"/static/uploads/{filename}"

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
def home():
    cars = []
    batts = []

    try:
        resp = requests.get(
            f"{LISTING_URL}/listings/?approved=1&product_type=car&sort=created_desc&per_page=12",
            timeout=5,
        )
        if resp.ok and resp.headers.get("content-type", "").startswith("application/json"):
            cars = resp.json().get("items", [])
    except requests.RequestException:
        cars = []

    try:
        resp = requests.get(
            f"{LISTING_URL}/listings/?approved=1&product_type=battery&sort=created_desc&per_page=12",
            timeout=5,
        )
        if resp.ok and resp.headers.get("content-type", "").startswith("application/json"):
            batts = resp.json().get("items", [])
    except requests.RequestException:
        batts = []

    return render_template("index.html", cars=cars, batts=batts)

@app.route("/compare", methods=["GET"], endpoint="compare_page")
def compare_page():
    return render_template("compare.html")


@app.route("/search", methods=["GET"], endpoint="search_page")
def search_page():
    """Search page for vehicles and batteries with advanced filters"""
    return render_template("search.html")


@app.route("/vehicles/<int:vehicle_id>")
def vehicle_detail(vehicle_id):
    """Vehicle detail page"""
    try:
        r = requests.get(f"{LISTING_URL}/listings/{vehicle_id}", timeout=5)
        if r.ok:
            product = r.json()
            if product.get('product_type') == 'car':
                return render_template("vehicle_detail.html", vehicle=product)
            else:
                flash("San pham khong phai xe dien.", "error")
                return redirect(url_for("search_page"))
        else:
            flash("Khong tim thay xe dien.", "error")
            return redirect(url_for("search_page"))
    except requests.RequestException:
        flash("Loi ket noi den he thong.", "error")
        return redirect(url_for("search_page"))


@app.route("/batteries/<int:battery_id>")
def battery_detail(battery_id):
    """Battery detail page"""
    try:
        r = requests.get(f"{LISTING_URL}/listings/{battery_id}", timeout=5)
        if r.ok:
            product = r.json()
            if product.get('product_type') == 'battery':
                return render_template("battery_detail.html", battery=product)
            else:
                flash("San pham khong phai pin.", "error")
                return redirect(url_for("search_page"))
        else:
            flash("Khong tim thay pin.", "error")
            return redirect(url_for("search_page"))
    except requests.RequestException:
        flash("Loi ket noi den he thong.", "error")
        return redirect(url_for("search_page"))



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
    # Best-effort: resolve seller_id if missing by looking up listing owner -> auth lookup
    if not seller_id:
        try:
            lr = requests.get(f"{LISTING_URL}/listings/{item_id}", timeout=4)
            if lr.ok and lr.headers.get("content-type", "").startswith("application/json"):
                owner = (lr.json() or {}).get("owner")
                if owner:
                    try:
                        ur = requests.get(f"{AUTH_URL}/auth/lookup", params={"username": owner}, timeout=4)
                        if ur.ok and ur.headers.get("content-type", "").startswith("application/json"):
                            seller_id = (ur.json() or {}).get("id") or seller_id
                    except requests.RequestException:
                        pass
        except requests.RequestException:
            pass
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
        # Use listing service for all items
        item_id = it.get('item_id')
        if item_id:
            ir = requests.get(f"{LISTING_URL}/listings/{item_id}", timeout=5)
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
        flash('Giß╗Å h├áng trß╗æng.', 'error')
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
    """Tạo payment từ cart và redirect đến payment checkout"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    cart = _get_cart()
    if not cart:
        return {"error": "empty_cart"}, 400
    
    # Get payment method from request
    data = request.get_json(silent=True) or {}
    payment_method = data.get('payment_method', 'cash')
    
    # Calculate total amount from cart
    total_amount = 0
    items_detail = []
    for it in cart:
        info = _enrich_item(it)
        price = it.get('price') or (info.get('price') if info else 0)
        qty = it.get('qty', 1)
        line_total = price * qty
        raw_seller = it.get('seller_id')
        try:
            normalized_seller = int(raw_seller) if raw_seller is not None else 1
        except (TypeError, ValueError):
            normalized_seller = 1
        total_amount += line_total
        items_detail.append({
            'item_type': it.get('item_type'),
            'item_id': it.get('item_id'),
            'seller_id': normalized_seller,
            'quantity': qty,
            'price': price,
            'total': line_total,
            'name': info.get('name') if info else 'Unknown'
        })
    
    # Generate unique order_id
    import uuid
    order_id = f"ORD-{user['sub']}-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"
    
    # Get first seller_id (for simple case, or could be platform/admin)
    # Default to 1 if no seller_id found
    seller_id = items_detail[0].get('seller_id', 1) if items_detail else 1
    
    # Create payment in payment-service
    payment_payload = {
        'order_id': order_id,
        'buyer_id': user['sub'],  # Add buyer_id from user
        'seller_id': seller_id,
        'amount': total_amount,
        'method': payment_method,  # Use selected payment method
        'cart_items': items_detail  # Store cart info in payment
    }
    
    try:
        print(f"[GATEWAY] Creating payment with payload: {payment_payload}")
        r = requests.post(f"{PAYMENT_URL}/payment/create", json=payment_payload, timeout=5)
        print(f"[GATEWAY] Payment service response status: {r.status_code}")
        print(f"[GATEWAY] Payment service response body: {r.text}")
        if r.ok:
            payment_data = r.json()
            payment_id = payment_data.get('payment_id') or payment_data.get('id')
            
            # Create contract from payment
            contract_payload = {
                'payment_id': payment_id,
                'product_info': {
                    'details': '\n'.join([f"- {item['name']} x{item['quantity']}: {item['total']:,.0f} VNĐ" for item in items_detail])
                },
                'buyer_info': {
                    'name': user.get('name', user.get('email', 'N/A')),
                    'email': user.get('email', 'N/A'),
                    'phone': user.get('phone', 'N/A')
                },
                'seller_info': {
                    'name': 'EV Trading Platform',
                    'email': 'support@evtrading.vn',
                    'phone': '1900-xxxx'
                },
                # Persist full cart items so callbacks can rebuild orders/transactions without session
                'cart_items': items_detail
            }
            
            contract_r = requests.post(f"{PAYMENT_URL}/payment/contract/create-from-payment", 
                                      json=contract_payload, timeout=5)
            
            if contract_r.ok:
                contract_data = contract_r.json()
                contract_id = contract_data.get('contract_id')
                print(f"[GATEWAY] Contract created: {contract_id}")
            else:
                print(f"[GATEWAY] Contract creation failed: {contract_r.text}")
                # Continue even if contract fails
                contract_id = None
            
            # Store payment_id and contract_id in session
            session['pending_payment'] = {
                'payment_id': payment_id,
                'contract_id': contract_id,
                'order_id': order_id,
                'cart': cart
            }
            
            # Redirect to contract signing page
            redirect_url = f"/contract/sign/{contract_id}" if contract_id else f"/payment/checkout/{payment_id}"
            return {"ok": True, "payment_id": payment_id, "contract_id": contract_id, "redirect": redirect_url}
        else:
            return {"error": "payment_creation_failed", "detail": r.text}, r.status_code
    except requests.RequestException as e:
        return {"error": "payment_service_unavailable", "detail": str(e)}, 503


@app.route("/listings/new", methods=["GET", "POST"], endpoint="add_listing")
def add_listing():
    user = session.get("user")
    if not user:
        session["next_after_login"] = url_for("add_listing")
        flash("Vui lòng đăng nhập để đăng tin.", "error")
        return redirect(url_for("login_page"))

    if request.method == "POST":
        # Helper function to parse numbers with thousand separators
        def parse_number(value, default=0):
            if not value:
                return default
            # Remove thousand separators (dots and commas)
            cleaned = str(value).replace(".", "").replace(",", "").strip()
            try:
                return int(cleaned)
            except ValueError:
                return default
        
        payload = {
            "product_type": (request.form.get("product_type") or "car").strip(),
            "name": (request.form.get("name") or "").strip(),
            "description": (request.form.get("description") or "").strip(),
            "price": parse_number(request.form.get("price"), 0),
            "brand": (request.form.get("brand") or "").strip(),
            "province": (request.form.get("province") or "").strip(),
            "year": parse_number(request.form.get("year"), 0),
            "mileage": parse_number(request.form.get("mileage"), 0),
            "battery_capacity": (request.form.get("battery_capacity") or "").strip(),
        }
        if not payload["name"] or payload["price"] <= 0:
            flash("Nhập các thông tin bắt buộc!", "error")
            return render_template("post_product.html")

        main_url = save_image(request.files.get("main_image"), prefix=f"{user['username']}_main")
        sub_urls = []
        for file in request.files.getlist("sub_images"):
            url = save_image(file, prefix=f"{user['username']}_sub")
            if url:
                sub_urls.append(url)

        body = payload | {"main_image_url": main_url, "sub_image_urls": sub_urls}

        try:
            resp = requests.post(
                f"{LISTING_URL}/listings/",
                json=body,
                headers={"Authorization": f"Bearer {session.get('access_token', '')}"},
                timeout=8,
            )
        except requests.RequestException:
            flash("Không kết nối được Listing service.", "error")
            return render_template("post_product.html")

        if resp.status_code == 201:
            flash("Đăng tin thành công! Bài đang chờ admin duyệt.", "success")
            return redirect(url_for("home"))

        message = None
        if resp.headers.get("content-type", "").startswith("application/json"):
            try:
                message = resp.json().get("error")
            except Exception:
                message = None
        flash(message or "Đăng tin thất bại.", "error")

    return render_template("post_product.html")


@app.get("/listings/<int:pid>")
def product_detail(pid):
    try:
        resp = requests.get(f"{LISTING_URL}/listings/{pid}", timeout=6)
        if not resp.ok or not resp.headers.get("content-type", "").startswith("application/json"):
            flash("Không tải được thông tin sản phẩm.", "error")
            return redirect(url_for("home"))
        item = resp.json()
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")
        return redirect(url_for("home"))

    return render_template("product_detail.html", item=item)

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
            # Always redirect to next_url or home, admin can navigate to /admin manually
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
        hoten = request.form.get("hoten", "").strip()
        sdt = request.form.get("sdt", "").strip()

        if password != confirm:
            flash("Mật khẩu xác nhận không khớp.", "error")
            return render_template("register.html")

        try:
            payload = {
                "username": username,
                "email": email,
                "password": password
            }
            if hoten:
                payload["full_name"] = hoten
            if sdt:
                payload["phone"] = sdt
            
            r = requests.post(
                f"{AUTH_URL}/auth/register",
                json=payload,
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

@app.get("/admin/logout", endpoint="admin_logout")
def admin_logout():
    # Only clear admin session keys; preserve normal user session
    session.pop("admin_user", None)
    session.pop("admin_access_token", None)
    flash("Đã đăng xuất admin!", "success")
    return redirect(url_for("admin_page"))

@app.route("/profile", methods=["GET", "POST"], endpoint="profile_page_gateway")
def profile_page_gateway():
    user = get_current_user()
    if not user:
        session["next_after_login"] = url_for("profile_page_gateway")
        return redirect(url_for("login_page"))
    
    if request.method == "POST":
        # Handle profile update
        try:
            headers = {"Authorization": f"Bearer {session.get('access_token')}"}
            files = {}
            if 'avatar' in request.files and request.files['avatar'].filename:
                files['avatar'] = request.files['avatar']
            
            # POST to auth/profile with form data
            r = requests.post(
                f"{AUTH_URL}/auth/profile",
                data=request.form,
                files=files if files else None,
                headers=headers,
                timeout=10
            )

            if r.ok:
                # Get response from POST
                post_response = r.json() if r.headers.get('content-type','').startswith('application/json') else {}
                print(f"[DEBUG] POST response: {post_response}")
                
                # Refresh session with new data
                try:
                    pr = requests.get(f"{AUTH_URL}/auth/profile", headers=headers, timeout=3)
                    if pr.ok and pr.headers.get('content-type','').startswith('application/json'):
                        pdata = pr.json()
                        new_user = pdata.get('user', {})
                        profile_obj = pdata.get('profile', {})
                        
                        print(f"[DEBUG] Profile GET response - user: {new_user}")
                        print(f"[DEBUG] Profile GET response - profile: {profile_obj}")
                        
                        # Update session - start fresh
                        su = session.get('user', {}).copy() if session.get('user') else {}
                        
                        # Update username from full_name
                        if profile_obj.get('full_name'):
                            su['username'] = profile_obj['full_name']
                        elif new_user.get('username'):
                            su['username'] = new_user['username']
                        
                        # Update avatar_url - prioritize profile over user
                        avatar = profile_obj.get('avatar_url') or new_user.get('avatar_url')
                        if avatar:
                            # Always build full path for consistency
                            if avatar.startswith('http://') or avatar.startswith('https://'):
                                su['avatar_url'] = avatar
                            elif avatar.startswith('/'):
                                su['avatar_url'] = avatar
                            else:
                                # Relative path - prepend /static/uploads/avatars/
                                su['avatar_url'] = f"/static/uploads/avatars/{avatar}"
                        else:
                            # Clear avatar if none provided
                            su.pop('avatar_url', None)
                        
                        # Update other fields
                        if new_user.get('email'):
                            su['email'] = new_user['email']
                        if new_user.get('role'):
                            su['role'] = new_user['role']
                        if new_user.get('id'):
                            su['id'] = new_user['id']
                        
                        print(f"[DEBUG] Updated session user: {su}")
                        session['user'] = su
                        session.modified = True
                except Exception as e:
                    print(f"[ERROR] Error updating session: {e}")
                    import traceback
                    traceback.print_exc()

                flash("Cập nhật hồ sơ thành công!", "success")
                return redirect(url_for("home"))
            else:
                error_msg = r.json().get("error", "Unknown error") if r.headers.get("content-type", "").startswith("application/json") else "Update failed"
                flash(f"Cập nhật thất bại: {error_msg}", "error")
        except requests.Timeout:
            flash("Auth service timeout, thử lại sau.", "error")
        except requests.RequestException as e:
            flash(f"Lỗi kết nối: {str(e)[:50]}", "error")
        
        return redirect(url_for("profile_page_gateway"))
    
    # GET - Fetch profile from auth service
    profile_data = {"profile": {}, "user": {}}
    try:
        headers = {"Authorization": f"Bearer {session.get('access_token')}"}
        r = requests.get(f"{AUTH_URL}/auth/profile", headers=headers, timeout=3)
        if r.ok and r.headers.get("content-type", "").startswith("application/json"):
            profile_data = r.json()
        else:
            flash("Không lấy được thông tin profile.", "warning")
    except requests.Timeout:
        flash("Auth service đang quá tải, vui lòng thử lại.", "warning")
    except requests.RequestException as e:
        flash(f"Lỗi kết nối: {str(e)[:50]}", "error")
    
    return render_template("profile.html", 
                         user=user, 
                         profile=profile_data.get("profile", {}),
                         user_info=profile_data.get("user", {}))

@app.get("/api/profile", endpoint="api_get_profile")
def api_get_profile():
    """API proxy to get user profile"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        headers = {"Authorization": f"Bearer {session.get('access_token')}"}
        r = requests.get(f"{AUTH_URL}/auth/profile", headers=headers, timeout=5)
        if r.ok:
            return (r.json(), 200)
        return (r.json() if r.headers.get("content-type", "").startswith("application/json") else {"error": "profile_error"}, r.status_code)
    except requests.RequestException as e:
        return {"error": "auth_unavailable", "message": str(e)[:100]}, 503

@app.put("/api/profile", endpoint="api_update_profile")
def api_update_profile():
    """API proxy to update user profile"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        headers = {"Authorization": f"Bearer {session.get('access_token')}"}
        r = requests.put(f"{AUTH_URL}/auth/profile", json=request.get_json(), headers=headers, timeout=5)
        if r.ok:
            # If auth service returned updated user info, refresh session copy
            try:
                data = r.json()
                updated_user = data.get('user') if isinstance(data, dict) else None
                profile_obj = data.get('profile') if isinstance(data, dict) else None
                if updated_user:
                    session['user'] = updated_user
                elif profile_obj and isinstance(profile_obj, dict):
                    su = session.get('user', {}) or {}
                    if profile_obj.get('full_name'):
                        su['username'] = profile_obj.get('full_name')
                    if profile_obj.get('avatar_url'):
                        su['avatar_url'] = profile_obj.get('avatar_url')
                    session['user'] = su
            except Exception:
                pass
            return (r.json(), 200)
        return (r.json() if r.headers.get("content-type", "").startswith("application/json") else {"error": "update_failed"}, r.status_code)
    except requests.RequestException as e:
        return {"error": "auth_unavailable", "message": str(e)[:100]}, 503

@app.post("/api/profile", endpoint="api_upload_avatar")
def api_upload_avatar():
    """API proxy to upload avatar (multipart form)"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        headers = {"Authorization": f"Bearer {session.get('access_token')}"}
        files = {}
        
        # Forward the file with original filename
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename:
                # Read file content and recreate with proper filename
                files['avatar'] = (file.filename, file.stream, file.content_type or 'application/octet-stream')
        
        r = requests.post(
            f"{AUTH_URL}/auth/profile",
            data=request.form,
            files=files if files else None,
            headers=headers,
            timeout=10
        )
        if r.ok:
            # Refresh session user if auth returned updated user info
            try:
                data = r.json()
                updated_user = data.get('user') if isinstance(data, dict) else None
                profile_obj = data.get('profile') if isinstance(data, dict) else None
                if updated_user:
                    session['user'] = updated_user
                elif profile_obj and isinstance(profile_obj, dict):
                    su = session.get('user', {}) or {}
                    if profile_obj.get('full_name'):
                        su['username'] = profile_obj.get('full_name')
                    if profile_obj.get('avatar_url'):
                        su['avatar_url'] = profile_obj.get('avatar_url')
                    session['user'] = su
            except Exception:
                pass
            return (r.json(), 200)
        return (r.json() if r.headers.get("content-type", "").startswith("application/json") else {"error": "upload_failed"}, r.status_code)
    except requests.RequestException as e:
        return {"error": "auth_unavailable", "message": str(e)[:100]}, 503

@app.get("/api/listings/<int:listing_id>")
def api_get_listing(listing_id):
    """API to get a single listing by ID"""
    try:
        r = requests.get(f"{LISTING_URL}/listings/{listing_id}", timeout=5)
        if r.ok:
            return (r.json(), 200)
        return {"error": "not_found"}, 404
    except requests.RequestException:
        return {"error": "service_unavailable"}, 503

@app.get("/api/listings/mine", endpoint="api_my_listings")
def api_my_listings():
    """API to get current user's listings"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        # Get user's listings from listing service
        r = requests.get(f"{LISTING_URL}/listings/?owner={user.get('username', user['sub'])}", timeout=5)
        if r.ok:
            return (r.json(), 200)
        return {"items": []}, 200
    except requests.RequestException:
        return {"items": []}, 200

@app.get("/api/payments/mine", endpoint="api_my_payments")
def api_my_payments():
    """API to get current user's payment history"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        # Forward query params and default to tab=all so seller transactions show up too
        params = dict(request.args)
        if not params.get('tab'):
            params['tab'] = 'all'
        r = requests.get(
            f"{TRANSACTIONS_URL}/transactions/user/{user['sub']}",
            params=params,
            timeout=5
        )
        if r.ok:
            return (r.json(), 200)
        return {"items": []}, 200
    except requests.RequestException:
        return {"items": []}, 200

@app.route("/add", methods=["GET"], endpoint="add_listing_page")
def add_listing_page():
    """Trang ─æ─âng tin (xe ─æiß╗çn hoß║╖c pin)"""
    user = get_current_user()
    if not user:
        session["next_after_login"] = url_for("add_listing_page")
        return redirect(url_for("login_page"))
    
    # Render form cho ng╞░ß╗¥i d├╣ng chß╗ìn loß║íi (xe/pin) v├á nhß║¡p th├┤ng tin
    # Tß║ím thß╗¥i redirect vß╗ü trang chß╗º vß╗¢i th├┤ng b├ío
    flash("T├¡nh n─âng ─æ─âng tin ─æang ─æ╞░ß╗úc ph├ít triß╗ân.", "info")
    return redirect(url_for("home"))

@app.route("/policy", methods=["GET"], endpoint="policy_page")
def policy_page():
    """Trang ch├¡nh s├ích"""
    return render_template("policy.html")

@app.route("/admin", methods=["GET"], endpoint="admin_page")
def admin_page():
    users = []
    products = []
    transactions = []

    if is_admin_session():
        try:
            headers = {"Authorization": f"Bearer {session.get('admin_access_token','')}"}
            r = requests.get(f"{AUTH_URL}/auth/admin/users", headers=headers, timeout=5)
            if r.ok and r.headers.get("content-type","").startswith("application/json"):
                users = r.json().get("data", [])
            else:
                flash("Không lấy được danh sách người dùng.", "error")
        except requests.RequestException:
            flash("Không kết nối được auth service.", "error")
        
        # Load transactions for admin
        try:
            r = requests.get(f"{TRANSACTIONS_URL}/transactions/admin/all?per_page=50", timeout=5)
            if r.ok and r.headers.get("content-type","").startswith("application/json"):
                tx_data = r.json()
                transactions = tx_data.get("data", [])

                # Build a map user_id -> username for buyer name enrichment
                user_map = {}
                try:
                    for u in users:
                        uid = u.get('id') or u.get('user_id')
                        if uid is not None:
                            user_map[int(uid)] = u.get('username') or u.get('email') or f"User #{uid}"
                except Exception:
                    user_map = {}

                # Enrich transactions with product owner (seller) and buyer names
                for tx in transactions:
                    # Buyer enrichment based on transaction_type
                    buyer_id = None
                    ttype = tx.get('transaction_type')
                    if ttype == 'order_purchase':
                        buyer_id = tx.get('user_id')
                    elif ttype == 'order_sale':
                        buyer_id = tx.get('partner_id')
                    else:
                        buyer_id = tx.get('user_id')
                    try:
                        if buyer_id is not None:
                            tx['buyer_name'] = user_map.get(int(buyer_id))
                    except Exception:
                        pass

                    # Seller enrichment from listing-service using item.id
                    try:
                        item = tx.get('item') or {}
                        item_id = item.get('id')
                    except Exception:
                        item_id = None
                    if item_id:
                        try:
                            prod_r = requests.get(f"{LISTING_URL}/listings/{item_id}", timeout=3)
                            if prod_r.ok and prod_r.headers.get('content-type','').startswith('application/json'):
                                product = prod_r.json()
                                tx['seller_name'] = product.get('owner')
                        except Exception:
                            pass
        except requests.RequestException:
            flash("Không kết nối được transactions service.", "error")

    try:
        resp = requests.get(f"{LISTING_URL}/listings/?sort=created_desc", timeout=8)
        if resp.ok and resp.headers.get("content-type", "").startswith("application/json"):
            data = resp.json()
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
        flash("Vui l├▓ng nhß║¡p ─æß║ºy ─æß╗º th├┤ng tin.", "error")
        return redirect(url_for("admin_page"))

    try:
        r = requests.post(
            f"{AUTH_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=5,
        )
    except requests.RequestException:
        flash("Kh├┤ng kß║┐t nß╗æi ─æ╞░ß╗úc Auth service.", "error")
        return redirect(url_for("admin_page"))

    if not r.ok:
        flash("─É─âng nhß║¡p thß║Ñt bß║íi.", "error")
        return redirect(url_for("admin_page"))

    token = r.json().get("access_token")
    if not token:
        flash("Auth service kh├┤ng trß║ú vß╗ü access_token.", "error")
        return redirect(url_for("admin_page"))

    try:
        payload = decode_token(token)
    except Exception:
        flash("Token kh├┤ng hß╗úp lß╗ç.", "error")
        return redirect(url_for("admin_page"))

    if payload.get("role") != "admin":
        flash("T├ái khoß║ún kh├┤ng phß║úi admin.", "error")
        return redirect(url_for("admin_page"))

    # Store admin session separately, do not override normal user session
    session["admin_access_token"] = token
    session["admin_user"] = payload
    flash("Đăng nhập admin thành công!", "success")
    return redirect(url_for("admin_page"))


@app.post("/admin/approve/<int:pid>")
@app.get("/admin/approve/<int:pid>")
def approve_product(pid):
    if not is_admin_session():
        session["next_after_login"] = url_for("approve_product", pid=pid)
        return redirect(url_for("login_page"))

    try:
        resp = requests.put(
            f"{LISTING_URL}/listings/{pid}/approve",
            headers={"Authorization": f"Bearer {session.get('admin_access_token', '')}"},
        )
        if resp.ok:
            flash("✅ Đã duyệt bài đăng.", "success")
        else:
            message = None
            if resp.headers.get("content-type", "").startswith("application/json"):
                try:
                    message = resp.json().get("error")
                except Exception:
                    message = None
            flash(message or "Không duyệt được bài đăng.", "error")
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")

    return redirect(url_for("admin_page"))


@app.get("/admin/delete/<int:pid>")
def delete_product(pid):
    if not is_admin_session():
        session["next_after_login"] = url_for("delete_product", pid=pid)
        return redirect(url_for("login_page"))

    try:
        resp = requests.delete(
            f"{LISTING_URL}/listings/{pid}",
            headers={"Authorization": f"Bearer {session.get('admin_access_token', '')}"},
        )
        if resp.ok:
            flash("Đã xoá bài đăng.", "success")
        else:
            message = None
            if resp.headers.get("content-type", "").startswith("application/json"):
                try:
                    message = resp.json().get("error")
                except Exception:
                    message = None
            flash(message or "Xoá thất bại.", "error")
    except requests.RequestException:
        flash("Không kết nối được listing service.", "error")

    return redirect(url_for("admin_page"))

@app.route("/admin/approve_user/<int:user_id>", methods=["POST", "GET"])
def approve_user(user_id):
    if not is_admin_session():
        session["next_after_login"] = url_for("approve_user", user_id=user_id)
        return redirect(url_for("login_page"))
    try:
        headers = {"Authorization": f"Bearer {session.get('admin_access_token','')}", "Content-Type": "application/json"}
        r = requests.patch(
            f"{AUTH_URL}/auth/users/{user_id}/status",
            json={"status": "approved"},
            headers=headers,
            timeout=5,
        )
        flash("─É├ú duyß╗çt t├ái khoß║ún." if r.ok else "Duyß╗çt thß║Ñt bß║íi.", "success" if r.ok else "error")
    except requests.RequestException:
        flash("Kh├┤ng kß║┐t nß╗æi ─æ╞░ß╗úc auth service.", "error")
    return redirect(url_for("admin_page"))

@app.get("/admin/delete_user/<int:user_id>", endpoint="delete_user")
def delete_user(user_id):
    if not is_admin_session():
        session["next_after_login"] = url_for("delete_user", user_id=user_id)
        return redirect(url_for("login_page"))
    try:
        headers = {"Authorization": f"Bearer {session.get('admin_access_token','')}", "Content-Type": "application/json"}
        r = requests.patch(
            f"{AUTH_URL}/auth/users/{user_id}/status",
            json={"status": "locked"},
            headers=headers,
            timeout=5,
        )
        if r.ok:
            flash("─É├ú kh├│a t├ái khoß║ún (thay cho x├│a).", "success")
        else:
            flash("Kh├│a t├ái khoß║ún thß║Ñt bß║íi.", "error")
    except requests.RequestException:
        flash("Kh├┤ng kß║┐t nß╗æi ─æ╞░ß╗úc auth service.", "error")
    return redirect(url_for("admin_page"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

# ======= API proxy minimal endpoints =======
@app.get('/api/search/vehicles')
def api_search_vehicles():
    """Search vehicles using search service with advanced filters"""
    try:
        params = dict(request.args)
        params['product_type'] = 'car'
        params['approved'] = '1'  # Only show approved listings
        
        r = requests.get(f"{SEARCH_URL}/search/listings", params=params, timeout=5)
        if r.ok:
            data = r.json()
            # Convert to expected format for frontend
            return {
                "items": data.get("items", []),
                "page": data.get("page", 1),
                "size": data.get("per_page", 12),
                "total": data.get("total", 0)
            }
        return {"error": "search_unavailable"}, 503
    except requests.RequestException:
        return {"error": "search_unavailable"}, 503

@app.get('/api/search/batteries')
def api_search_batteries():
    """Search batteries using search service with advanced filters"""
    try:
        params = dict(request.args)
        params['product_type'] = 'battery'
        params['approved'] = '1'  # Only show approved listings
        
        r = requests.get(f"{SEARCH_URL}/search/listings", params=params, timeout=5)
        if r.ok:
            data = r.json()
            # Convert to expected format for frontend
            return {
                "items": data.get("items", []),
                "page": data.get("page", 1),
                "size": data.get("per_page", 12),
                "total": data.get("total", 0)
            }
        return {"error": "search_unavailable"}, 503
    except requests.RequestException:
        return {"error": "search_unavailable"}, 503

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
                # Use listing service for all items
                item_id = f.get('item_id')
                if item_id:
                    ir = requests.get(f"{LISTING_URL}/listings/{item_id}", timeout=5)
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
        return {"error": "unauthenticated", "message": "Vui l├▓ng ─æ─âng nhß║¡p"}, 401
    
    d = request.get_json(force=True)
    if not d.get('item_type') or not d.get('item_id'):
        return {"error": "missing_fields", "message": "Thiß║┐u th├┤ng tin sß║ún phß║⌐m"}, 400
    
    d['user_id'] = user['sub']
    
    try:
        r = requests.post(f"{FAVORITES_URL}/favorites", json=d, timeout=5)
        if r.ok:
            return (r.json() if r.headers.get('content-type','').startswith('application/json') else {"ok": True}, r.status_code)
        else:
            # Forward error from favorites service
            error_data = r.json() if r.headers.get('content-type','').startswith('application/json') else {"error": "unknown"}
            return (error_data, r.status_code)
    except requests.Timeout:
        return {"error": "timeout", "message": "Favorites service qu├í tß║úi"}, 503
    except requests.RequestException as e:
        return {"error": "favorites_unavailable", "message": str(e)[:100]}, 503

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


# ===== Transaction History API Routes =====
@app.get('/api/transactions/user/<int:user_id>')
def api_get_user_transactions(user_id: int):
    """API lß║Ñy giao dß╗ïch cß╗ºa user (mua h├áng + b├ín h├áng)"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    # Security: user chß╗ë xem ─æ╞░ß╗úc GD cß╗ºa m├¼nh, trß╗½ admin
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
    """API lß║Ñy lß╗ïch sß╗¡ v├¡ ─æiß╗çn tß╗¡"""
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
    """API lß║Ñy chi tiß║┐t giao dß╗ïch + timeline"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        r = requests.get(f"{TRANSACTIONS_URL}/transactions/{transaction_id}", timeout=5)
        if r.ok:
            data = r.json()
            # Security check: user phß║úi l├á ng╞░ß╗¥i tham gia GD
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


# ===== Payment Routes =====
@app.post('/api/payment/create')
def api_create_payment():
    """Tạo giao dịch thanh toán mới"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    data = request.get_json(force=True)
    data['buyer_id'] = user['sub']
    
    try:
        r = requests.post(f"{PAYMENT_URL}/payment/create", json=data, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "payment_unavailable"}, 503


@app.get('/contract/sign/<int:contract_id>')
def contract_signing_page(contract_id: int):
    """Trang ký hợp đồng điện tử"""
    user = get_current_user()
    if not user:
        session['next_after_login'] = url_for('contract_signing_page', contract_id=contract_id)
        return redirect(url_for('login_page'))
    
    return render_template('contract_signing.html', contract_id=contract_id, user=user)


@app.get('/payment/checkout/<int:payment_id>')
def payment_checkout_page(payment_id: int):
    """Trang thanh toán với VietQR"""
    user = get_current_user()
    if not user:
        session['next_after_login'] = url_for('payment_checkout_page', payment_id=payment_id)
        return redirect(url_for('login_page'))
    
    # Use the clean v2 template to avoid legacy corrupted file issues
    return render_template('payment_checkout_v2.html', payment_id=payment_id, user=user)


@app.get('/payment/thankyou/<int:payment_id>')
def payment_thankyou_page(payment_id: int):
    """Trang cảm ơn sau khi xác nhận chuyển tiền"""
    user = get_current_user()
    if not user:
        session['next_after_login'] = url_for('payment_thankyou_page', payment_id=payment_id)
        return redirect(url_for('login_page'))
    
    return render_template('payment_thankyou.html', payment_id=payment_id, user=user)


@app.post('/api/payment/confirm/<int:payment_id>')
def api_confirm_payment(payment_id: int):
    """Xác nhận thanh toán"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    data = request.get_json(force=True)
    
    try:
        r = requests.post(f"{PAYMENT_URL}/payment/confirm/{payment_id}", json=data, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "payment_unavailable"}, 503


@app.get('/payment/invoice/<int:contract_id>')
def payment_invoice_page(contract_id: int):
    """Trang hóa đơn"""
    user = get_current_user()
    if not user:
        session['next_after_login'] = url_for('payment_invoice_page', contract_id=contract_id)
        return redirect(url_for('login_page'))
    
    try:
        r = requests.get(f"{PAYMENT_URL}/payment/invoice/{contract_id}", timeout=5)
        if r.ok:
            return r.text, r.status_code, {'Content-Type': 'text/html'}
        flash('Invoice not found', 'error')
        return redirect(url_for('home'))
    except requests.RequestException:
        flash('Payment service unavailable', 'error')
        return redirect(url_for('home'))


@app.post('/api/payment/contract/sign')
def api_sign_contract():
    """Ký hợp đồng số hóa"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    data = request.get_json(force=True)
    data['signer_id'] = user['sub']
    data['signer_name'] = user.get('username', 'Unknown')
    
    try:
        r = requests.post(f"{PAYMENT_URL}/payment/contract/sign", json=data, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "payment_unavailable"}, 503


@app.get('/api/payment/contract/preview/<int:contract_id>')
def api_preview_contract(contract_id: int):
    """Xem trước hợp đồng"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        r = requests.get(f"{PAYMENT_URL}/payment/contract/preview/{contract_id}", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "payment_unavailable"}, 503


@app.post('/api/payment/simulate/<int:payment_id>')
def api_simulate_payment(payment_id: int):
    """Simulate payment for testing"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        r = requests.post(f"{PAYMENT_URL}/payment/simulate/{payment_id}", timeout=5)
        if r.ok:
            # After successful payment, create orders from cart
            _create_orders_from_payment(payment_id, user)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "payment_unavailable"}, 503


@app.get('/api/payment/<int:payment_id>')
def api_get_payment(payment_id: int):
    """Get payment details"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        r = requests.get(f"{PAYMENT_URL}/payment/{payment_id}", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "payment_unavailable"}, 503


@app.get('/api/payment/status/<int:payment_id>')
def api_payment_status(payment_id: int):
    """Check payment status with contract info"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401

    try:
        r = requests.get(f"{PAYMENT_URL}/payment/status/{payment_id}", timeout=5)
        if r.ok:
            data = r.json()
            # Try to get contract info
            try:
                contract_r = requests.get(f"{PAYMENT_URL}/payment/{payment_id}", timeout=5)
                if contract_r.ok:
                    payment_data = contract_r.json()
                    # Add contract code if exists
                    if payment_data.get('contracts'):
                        contract = payment_data['contracts'][0]
                        # Include contract_id for client convenience
                        data['contract_id'] = contract.get('id')
                        data['contract_code'] = f"HD{contract.get('id', payment_id)}"
            except:
                pass
            return (data, r.status_code)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "payment_unavailable"}, 503


@app.get('/api/payment/contract/view/<int:contract_id>')
def api_contract_view(contract_id: int):
    """Get contract details"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        r = requests.get(f"{PAYMENT_URL}/payment/contract/view/{contract_id}", timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "contract_unavailable"}, 503


@app.post('/api/payment/contract/sign/<int:contract_id>')
def api_contract_sign(contract_id: int):
    """Sign contract"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    try:
        data = request.get_json()
        r = requests.post(f"{PAYMENT_URL}/payment/contract/sign/{contract_id}", 
                         json=data, timeout=5)
        return (r.json(), r.status_code)
    except requests.RequestException:
        return {"error": "contract_unavailable"}, 503


@app.post('/api/payment/callback/<int:payment_id>')
def payment_callback(payment_id: int):
    """Webhook callback sau khi payment completed - tạo orders và xóa cart"""
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    
    # Get payment info to verify it's completed (treat 'paid' as completed for bank transfer)
    try:
        r = requests.get(f"{PAYMENT_URL}/payment/{payment_id}", timeout=5)
        if not r.ok:
            return {"error": "payment_not_found"}, 404
        
        payment_data = r.json()
        if payment_data.get('status') in ('paid', 'completed'):
            # Create orders from stored cart
            orders_created = _create_orders_from_payment(payment_id, user)
            
            return {"ok": True, "order_ids": orders_created, "message": "Orders created successfully"}
        else:
            return {"error": "payment_not_completed", "status": payment_data.get('status')}, 400
    except requests.RequestException as e:
        return {"error": "payment_service_unavailable", "detail": str(e)}, 503


@app.route('/api/payment/finalize/<int:payment_id>', methods=['GET','POST'])
def api_payment_finalize(payment_id: int):
    """Manual finalize endpoint: create orders + transactions + mark-sold using session or contract fallback.
    Useful when previous step missed simulate/callback. Idempotency is best-effort (may create duplicates if called repeatedly).
    """
    user = get_current_user()
    if not user:
        return {"error": "unauthenticated"}, 401
    try:
        created = _create_orders_from_payment(payment_id, user)
        return {"ok": True, "order_ids": created, "count": len(created)}
    except Exception as e:
        return {"error": "finalize_failed", "detail": str(e)[:200]}, 500


def _create_orders_from_payment(payment_id: int, user: dict):
    """Helper function to create orders after payment completion.
    Prefer session cart; if unavailable, fallback to contract.extra_data.cart_items from payment-service.
    """
    cart = []

    # 1) Try session first
    pending = session.get('pending_payment', {})
    if pending.get('payment_id') == payment_id:
        cart = pending.get('cart', [])

    # 2) Fallback: fetch from payment-service contract.extra_data.cart_items
    if not cart:
        try:
            pr = requests.get(f"{PAYMENT_URL}/payment/{payment_id}", timeout=5)
            if pr.ok and pr.headers.get('content-type','').startswith('application/json'):
                pdata = pr.json()
                contracts = pdata.get('contracts') or []
                if contracts:
                    cid = contracts[0].get('id')
                    if cid:
                        cr = requests.get(f"{PAYMENT_URL}/payment/contract/view/{cid}", timeout=5)
                        if cr.ok and cr.headers.get('content-type','').startswith('application/json'):
                            cdata = cr.json()
                            extra = cdata.get('extra_data') or {}
                            cart_items = extra.get('cart_items') or []
                            # Normalize into cart format used by this function
                            normalized = []
                            for it in cart_items:
                                normalized.append({
                                    'item_type': it.get('item_type'),
                                    'item_id': it.get('item_id'),
                                    'seller_id': it.get('seller_id'),
                                    'price': it.get('price'),
                                    'qty': it.get('quantity', 1)
                                })
                            cart = normalized
        except requests.RequestException:
            cart = cart or []

    if not cart:
        return []
    created = []
    
    # Normalize buyer id once (session stores as str)
    try:
        buyer_id = int(user.get('sub'))
    except (TypeError, ValueError):
        buyer_id = user.get('sub')

    for it in cart:
        # Seller id might be missing from cart_items (older flows). Fallback to platform (1).
        raw_seller = it.get('seller_id')
        try:
            seller_id = int(raw_seller) if raw_seller is not None else 1
        except (TypeError, ValueError):
            seller_id = 1

        payload = {
            'buyer_id': buyer_id,
            'seller_id': seller_id,
            'item_type': it.get('item_type'),
            'item_id': it.get('item_id'),
            'price': it.get('price') or 0,
            'payment_id': payment_id  # Link order to payment
        }
        try:
            r = requests.post(f"{ORDERS_URL}/orders", json=payload, timeout=5)
            if r.ok:
                order_id = r.json().get('id')
                created.append(order_id)

                # Best-effort enrich item for snapshot fields
                item_obj = _enrich_item(it) or {}
                item_name = item_obj.get('name') or item_obj.get('title') or f"{it.get('item_type','item').title()} #{it.get('item_id')}"
                item_image = item_obj.get('main_image_url') or (item_obj.get('sub_image_urls') or [None])[0]

                amount = int(it.get('price') or item_obj.get('price') or 0)
                seller_id = seller_id or 1
                buyer_tx_user = buyer_id

                # Create two mirrored transactions: buyer purchase + seller sale
                tx_common = {
                    'order_id': order_id,
                    'item_type': it.get('item_type'),
                    'item_id': it.get('item_id'),
                    'item_name': item_name,
                    'item_image': item_image,
                    'amount': amount,
                    'fee': 0,
                    'net_amount': amount,
                    'payment_method': 'bank_transfer',
                    'status': 'completed',
                }

                try:
                    # Buyer-side transaction
                    buyer_tx = {
                        **tx_common,
                        'transaction_type': 'order_purchase',
                        'user_id': buyer_tx_user,
                        'partner_id': seller_id,
                        'description': f"Mua {item_name}"
                    }
                    requests.post(f"{TRANSACTIONS_URL}/transactions", json=buyer_tx, timeout=5)
                except requests.RequestException:
                    pass

                try:
                    # Seller-side transaction
                    seller_tx = {
                        **tx_common,
                        'transaction_type': 'order_sale',
                        'user_id': seller_id,
                        'partner_id': buyer_tx_user,
                        'description': f"Bán {item_name}"
                    }
                    requests.post(f"{TRANSACTIONS_URL}/transactions", json=seller_tx, timeout=5)
                except requests.RequestException:
                    pass

                # Mark listing as SOLD (hide by unapproving) - best effort
                try:
                    requests.put(f"{LISTING_URL}/listings/{it.get('item_id')}/mark-sold", timeout=5)
                except requests.RequestException:
                    pass
        except requests.RequestException:
            pass
    
    # Clear cart and pending payment after creating orders (session path only)
    if created and pending.get('payment_id') == payment_id:
        try:
            _save_cart([])
            session.pop('pending_payment', None)
        except Exception:
            pass
    
    return created


# Proxy static files from auth-service (avatars)
@app.route("/static/uploads/avatars/<path:filename>")
def proxy_avatar(filename):
    """Proxy avatar files from auth-service"""
    try:
        r = requests.get(f"{AUTH_URL}/static/uploads/avatars/{filename}", timeout=5)
        if r.ok:
            return Response(r.content, mimetype=r.headers.get('content-type', 'image/jpeg'))
        return "Not found", 404
    except requests.RequestException:
        return "Service unavailable", 503


@app.post("/ai/price_suggest")
def price_suggest():
    if request.content_type and request.content_type.startswith("application/json"):
        raw = request.get_json(silent=True) or {}
    else:
        raw = request.form.to_dict()

    product_type = (raw.get("product_type") or "car").strip().lower()
    name = (raw.get("name") or "").strip()
    brand = (raw.get("brand") or "").strip()
    province = (raw.get("province") or "").strip()
    year = _num(raw.get("year"))
    mileage = _num(raw.get("mileage"))
    cap_kwh = _num(raw.get("battery_capacity_kwh") or raw.get("battery_capacity"))
    description = (raw.get("description") or "").strip()

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
    except requests.exceptions.ReadTimeout as exc:
        app.logger.exception("pricing-service read timeout")
        return jsonify(error="pricing-service quá thời gian phản hồi", detail=str(exc)), 504
    except requests.exceptions.RequestException as exc:
        app.logger.exception("price_suggest failed: %s", exc)
        return jsonify(error="Không kết nối được pricing-service", detail=str(exc)), 502

    content_type = r.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        try:
            return jsonify(r.json()), r.status_code
        except Exception:
            pass
    return r.text, r.status_code, {"Content-Type": content_type or "text/plain"}

