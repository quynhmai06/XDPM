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
        "product_type": getattr(p, "product_type", "car"),
        "name": p.name,
        "description": p.description,
        "price": p.price,
        "brand": p.brand,
        "province": p.province,
        "year": p.year,
        "mileage": p.mileage,
        "battery_capacity": p.battery_capacity,
        # các field dưới có thể không tồn tại trong model → dùng getattr
        "battery_chemistry": getattr(p, "battery_chemistry", None),
        "soh_percent": getattr(p, "soh_percent", None),
        "cycle_count": getattr(p, "cycle_count", None),
        "owner": p.owner,
        "main_image_url": p.main_image_url,
        "sub_image_urls": json.loads(p.sub_image_urls or "[]"),
        "approved": p.approved,
        "approved_at": p.approved_at.isoformat() if p.approved_at else None,
        "approved_by": p.approved_by,
        "sold": getattr(p, "sold", False),
        "sold_at": p.sold_at.isoformat() if getattr(p, "sold_at", None) else None,
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
    """Danh sách tin đăng đơn giản - dùng search-service cho tìm kiếm nâng cao"""
    q = Product.query

    # Chỉ giữ lại các filter cơ bản cho homepage
    product_type = request.args.get("product_type")
    if product_type:
        q = q.filter(Product.product_type == product_type)

    owner = request.args.get("owner")
    if owner: q = q.filter(Product.owner == owner)

    approved = request.args.get("approved")
    if approved is not None:
        q = q.filter(Product.approved == (approved in ["1","true","True"]))
    
    # Ẩn sản phẩm đã bán khỏi tìm kiếm công khai (trừ khi owner xem lịch sử của mình)
    show_sold = request.args.get("show_sold")
    if show_sold not in ["1", "true", "True"]:
        q = q.filter(Product.sold == False)

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
        return jsonify(error="Nhập các thông tin bắt buộc!"), 400

    # Validate số
    year = parse_int(data.get("year"))
    mileage = parse_int(data.get("mileage"))
    sub_urls = data.get("sub_image_urls") or []
    if not isinstance(sub_urls, list):
        return jsonify(error="sub_image_urls phải là danh sách URL."), 400

    p = Product(
        product_type=(data.get("product_type") or "car").strip(),  # ✅ ghi loại sản phẩm
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
    if "product_type" in data:
        v = (data.get("product_type") or "").strip()
        if v: p.product_type = v

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

@bp.put("/<int:pid>/mark-sold")
def mark_sold(pid:int):
    """Đánh dấu tin đã bán - giữ nguyên trạng thái duyệt, chỉ set sold=True để ẩn khỏi tìm kiếm nhưng vẫn lưu trong lịch sử.
    Tạm thời không ràng buộc quyền để phục vụ demo/flow tự động. TODO: siết quyền (owner/admin/internal).
    """
    p = Product.query.get_or_404(pid)
    # Đánh dấu đã bán, không thay đổi approved
    p.sold = True
    p.sold_at = datetime.utcnow()
    p.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(message="Đã đánh dấu đã bán.", item=to_json(p))
