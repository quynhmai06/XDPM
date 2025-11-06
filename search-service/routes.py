from flask import Blueprint, request, jsonify
from models import db, Product
import json

bp = Blueprint("search", __name__, url_prefix="/search")


def parse_int(v, default=None, minv=None, maxv=None):
    if v is None or v == "": return default
    try:
        n = int(v)
        if minv is not None and n < minv: return default
        if maxv is not None and n > maxv: return default
        return n
    except:
        return default


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
        "owner": p.owner,
        "main_image_url": p.main_image_url,
        "sub_image_urls": json.loads(p.sub_image_urls or "[]"),
        "approved": p.approved,
        "approved_at": p.approved_at.isoformat() if p.approved_at else None,
        "approved_by": p.approved_by,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@bp.get("/")
def health():
    return {"service": "search", "status": "ok"}


@bp.get("/listings")
def search_products():
    """Tìm kiếm và lọc danh sách tin đăng"""
    q = Product.query

    # Tìm kiếm theo từ khóa
    kw = request.args.get("q", "").strip()
    if kw:
        like = f"%{kw}%"
        q = q.filter(db.or_(Product.name.ilike(like), Product.description.ilike(like)))

    # Lọc theo hãng
    brand = request.args.get("brand")
    if brand: 
        q = q.filter(Product.brand.ilike(f"%{brand}%"))

    # Lọc theo tỉnh/thành phố
    province = request.args.get("province")
    if province: 
        q = q.filter(Product.province == province)

    # Lọc theo loại sản phẩm (car/battery)
    product_type = request.args.get("product_type")
    if product_type:
        q = q.filter(Product.product_type == product_type)

    # Lọc theo chủ sở hữu
    owner = request.args.get("owner")
    if owner: 
        q = q.filter(Product.owner == owner)

    # Lọc theo trạng thái duyệt
    approved = request.args.get("approved")
    if approved is not None:
        q = q.filter(Product.approved == (approved in ["1","true","True"]))

    # Lọc theo giá
    min_price = parse_int(request.args.get("min_price"), None, 0)
    if min_price is not None:
        q = q.filter(Product.price >= min_price)

    max_price = parse_int(request.args.get("max_price"), None, 0)
    if max_price is not None:
        q = q.filter(Product.price <= max_price)

    # Lọc theo năm sản xuất
    year_from = parse_int(request.args.get("year_from"))
    if year_from is not None:
        q = q.filter(Product.year >= year_from)

    year_to = parse_int(request.args.get("year_to"))
    if year_to is not None:
        q = q.filter(Product.year <= year_to)

    # Lọc theo số km đã đi
    mileage_max = parse_int(request.args.get("mileage_max"))
    if mileage_max is not None:
        q = q.filter(Product.mileage <= mileage_max)

    # Sắp xếp
    sort = request.args.get("sort", "created_desc")
    if sort == "created_asc":
        q = q.order_by(Product.created_at.asc())
    elif sort == "price_asc":
        q = q.order_by(Product.price.asc())
    elif sort == "price_desc":
        q = q.order_by(Product.price.desc())
    else:
        q = q.order_by(Product.created_at.desc())

    # Phân trang
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


# Endpoint cũ không còn cần thiết - đã thay thế bằng /search/listings
