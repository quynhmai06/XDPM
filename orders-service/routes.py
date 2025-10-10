from flask import Blueprint, request
from models import db, Order

bp = Blueprint("orders", __name__, url_prefix="/orders")


@bp.get("/")
def health():
    return {"service": "orders", "status": "ok"}


@bp.post("")
def create_order():
    d = request.get_json(force=True)
    o = Order(
        buyer_id=d.get("buyer_id"),
        seller_id=d.get("seller_id"),
        item_type=d.get("item_type"),
        item_id=d.get("item_id"),
        price=d.get("price"),
        status="created",
    )
    db.session.add(o)
    db.session.commit()
    return {"id": o.id, "status": o.status}, 201


@bp.get("/history")
def history():
    user_id = request.args.get("user_id", type=int)
    role = request.args.get("role", "buyer")  # buyer|seller
    q = Order.query
    if user_id:
        q = q.filter(Order.buyer_id == user_id) if role == "buyer" else q.filter(Order.seller_id == user_id)
    data = [{
        "id": o.id,
        "buyer_id": o.buyer_id,
        "seller_id": o.seller_id,
        "item_type": o.item_type,
        "item_id": o.item_id,
        "price": o.price,
        "status": o.status,
        "created_at": o.created_at.isoformat(),
    } for o in q.order_by(Order.created_at.desc()).all()]
    return {"data": data}
