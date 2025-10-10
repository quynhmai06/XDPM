# listing-service/routes.py
from flask import Blueprint, request, jsonify
from models import db, Product
import os, jwt, json
from datetime import datetime

bp = Blueprint("listing", __name__, url_prefix="/listings")
JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")

# ---------- Auth helpers ----------
def current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "): 
        return None
    token = auth.split(" ", 1)[1].strip()
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None

def require_auth():
    u = current_user()
    if not u:
        return None, (jsonify(error="Unauthorized"), 401)
    return u, None

def require_admin():
    u = current_user()
    if not u or u.get("role") != "admin":
        return None, (jsonify(error="Forbidden"), 403)
    return u, None

# ---------- Utils ----------
def to_json(p: Product):
    return {
        "id": p.id,
        "product_type": p.product_type,   
        "name": p.name,
        "description": p.description,
        "price": p.price,
        "brand": p.brand,
        "province": p.province,
        "year": p.year,
        "mileage": p.mileage,
        "battery_capacity": p.battery_capacity,
        "battery_chemistry": p.battery_chemistry,
        "soh_percent": p.soh_percent,   
        "cycle_count": p.cycle_count,   
        "owner": p.owner,
        "main_image_url": p.main_image_url,
        "sub_image_urls": json.loads(p.sub_image_urls or "[]"),
        "approved": p.approved,
        "approved_at": p.approved_at.isoformat() if p.approved_at else None,
        "approved_by": p.approved_by,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }

def parse_int(v, default=None, minv=None, maxv=None):
    if v is None or v == "": return default
    try:
        n = int(v)
        if minv is not None and n < minv: return default
        if maxv is not None and n > maxv: return default
        return n
    except:
        return default

# ---------- Endpoints ----------

@bp.get("/")
def list_products():
    """
    Query params:
      q (search in name/description), brand, province,
      min_price, max_price, year_from, year_to, mileage_max,
      approved (0/1), owner (username),
      sort (created_desc|created_asc|price_asc|price_desc),
      page (default 1), per_page (<=50)
    """
    q = Product.query

    # Filters
    kw = request.args.get("q", "").strip()
    if kw:
        like = f"%{kw}%"
        q = q.filter(db.or_(Product.name.ilike(like), Product.description.ilike(like)))

    brand = request.args.get("brand")
    if brand: q = q.filter(Product.brand == brand)

    province = request.args.get("province")
    if province: q = q.filter(Product.province == province)

    owner = request.args.get("owner")
    if owner: q = q.filter(Product.owner == owner)

    approved = request.args.get("approved")
    if approved is not None:
        q = q.filter(Product.approved == (approved in ["1","true","True"]))

    min_price = parse_int(request.args.get("min_price"), None, 0)
    if min_price is not None:
        q = q.filter(Product.price >= min_price)

    max_price = parse_int(request.args.get("max_price"), None, 0)
    if max_price is not None:
        q = q.filter(Product.price <= max_price)

    year_from = parse_int(request.args.get("year_from"))
    if year_from is not None:
        q = q.filter(Product.year >= year_from)

    year_to = parse_int(request.args.get("year_to"))
    if year_to is not None:
        q = q.filter(Product.year <= year_to)

    mileage_max = parse_int(request.args.get("mileage_max"))
    if mileage_max is not None:
        q = q.filter(Product.mileage <= mileage_max)

    # Sort
    sort = request.args.get("sort", "created_desc")
    if sort == "created_asc":
        q = q.order_by(Product.created_at.asc())
    elif sort == "price_asc":
        q = q.order_by(Product.price.asc())
    elif sort == "price_desc":
        q = q.order_by(Product.price.desc())
    else:
        q = q.order_by(Product.created_at.desc())

    # Pagination
    page = parse_int(request.args.get("page"), 1, 1)
    per_page = parse_int(request.args.get("per_page"), 12, 1, 50)
    page_obj = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [to_json(p) for p in page_obj.items],
        "page": page_obj.page,
        "per_page": page_obj.per_page,
        "total": page_obj.total,
        "pages": page_obj.pages
    })

@bp.post("/")
def create_product():
    user, err = require_auth()
    if err: return err

    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    price = parse_int(data.get("price"), 0, 1)
    if not name or price <= 0:
        return jsonify(error="Thiếu tên hoặc giá không hợp lệ."), 400

    # Validate số
    year = parse_int(data.get("year"))
    mileage = parse_int(data.get("mileage"))
    sub_urls = data.get("sub_image_urls") or []
    if not isinstance(sub_urls, list):
        return jsonify(error="sub_image_urls phải là danh sách URL."), 400

    p = Product(
        name=name,
        description=data.get("description"),
        price=price,
        brand=data.get("brand"),
        province=data.get("province"),
        year=year,
        mileage=mileage,
        battery_capacity=data.get("battery_capacity"),
        owner=user["username"],
        main_image_url=data.get("main_image_url"),
        sub_image_urls=json.dumps(sub_urls),
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(id=p.id, message="Đăng tin thành công.", item=to_json(p)), 201

@bp.get("/<int:pid>")
def get_product(pid):
    p = Product.query.get_or_404(pid)
    return jsonify(to_json(p))

@bp.patch("/<int:pid>")
def update_product(pid):
    user, err = require_auth()
    if err: return err
    p = Product.query.get_or_404(pid)

    # chỉ owner mới sửa, và chỉ sửa khi chưa duyệt
    if user["username"] != p.owner and user.get("role") != "admin":
        return jsonify(error="Forbidden"), 403
    if p.approved and user.get("role") != "admin":
        return jsonify(error="Đã duyệt, không thể sửa."), 400

    data = request.get_json(force=True)
    if "name" in data:
        if not (data["name"] or "").strip():
            return jsonify(error="Tên không hợp lệ."), 400
        p.name = data["name"].strip()
    if "description" in data: p.description = data["description"]
    if "price" in data:
        price = parse_int(data["price"], None, 1)
        if price is None: return jsonify(error="Giá không hợp lệ."), 400
        p.price = price
    if "brand" in data: p.brand = data["brand"]
    if "province" in data: p.province = data["province"]
    if "year" in data:
        y = parse_int(data["year"])
        if y is None: return jsonify(error="Năm không hợp lệ."), 400
        p.year = y
    if "mileage" in data:
        m = parse_int(data["mileage"], None, 0)
        if m is None: return jsonify(error="Số km không hợp lệ."), 400
        p.mileage = m
    if "battery_capacity" in data: p.battery_capacity = data["battery_capacity"]
    if "main_image_url" in data: p.main_image_url = data["main_image_url"]
    if "sub_image_urls" in data:
        if not isinstance(data["sub_image_urls"], list):
            return jsonify(error="sub_image_urls phải là danh sách."), 400
        p.sub_image_urls = json.dumps(data["sub_image_urls"])

    db.session.commit()
    return jsonify(message="Đã cập nhật.", item=to_json(p))

@bp.put("/<int:pid>/approve")
def approve_product(pid):
    admin, err = require_admin()
    if err: return err
    p = Product.query.get_or_404(pid)
    p.approved = True
    p.approved_at = datetime.utcnow()
    p.approved_by = admin["username"]
    db.session.commit()
    return jsonify(message="Đã duyệt.", item=to_json(p))

@bp.put("/<int:pid>/unapprove")
def unapprove_product(pid):
    admin, err = require_admin()
    if err: return err
    p = Product.query.get_or_404(pid)
    p.approved = False
    p.approved_at = None
    p.approved_by = None
    db.session.commit()
    return jsonify(message="Đã bỏ duyệt.", item=to_json(p))

@bp.delete("/<int:pid>")
def delete_product(pid):
    u, err = require_auth()
    if err: return err
    p = Product.query.get_or_404(pid)

    # owner xóa được nếu chưa duyệt; admin xóa được luôn
    if u.get("role") == "admin":
        pass
    elif u["username"] == p.owner and not p.approved:
        pass
    else:
        return jsonify(error="Forbidden"), 403

    db.session.delete(p)
    db.session.commit()
    return jsonify(message="Đã xoá.")
