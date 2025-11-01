from flask import Blueprint, request
from models import db, Vehicle, Battery
from sqlalchemy import and_

bp = Blueprint("listings", __name__, url_prefix="/listings")


def _paginate(q, serializer):
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 10))
    items = q.limit(size).offset((page - 1) * size).all()
    total = q.count()
    return {
        "page": page,
        "size": size,
        "total": total,
        "items": [serializer(i) for i in items],
    }


def _vehicle_json(v: Vehicle):
    return {
        "id": v.id,
        "brand": v.brand,
        "model": v.model,
        "year": v.year,
        "km": v.km,
        "price": v.price,
        "condition": v.condition,
        "battery_capacity_kwh": v.battery_capacity_kwh,
        "seller_id": v.seller_id,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def _battery_json(b: Battery):
    return {
        "id": b.id,
        "brand": b.brand,
        "capacity_kwh": b.capacity_kwh,
        "cycles": b.cycles,
        "health_percent": b.health_percent,
        "price": b.price,
        "year": b.year,
        "condition": b.condition,
        "seller_id": b.seller_id,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


@bp.get("/")
def health():
    return {"service": "listings", "status": "ok"}


@bp.get("/vehicles")
def search_vehicles():
    brand = request.args.get("brand")
    model = request.args.get("model")
    year = request.args.get("year", type=int)
    year_min = request.args.get("year_min", type=int)
    year_max = request.args.get("year_max", type=int)
    km_min = request.args.get("km_min", type=int)
    km_max = request.args.get("km_max", type=int)
    price_min = request.args.get("price_min", type=int)
    price_max = request.args.get("price_max", type=int)
    condition = request.args.get("condition")
    cap_min = request.args.get("battery_capacity_min", type=float)
    cap_max = request.args.get("battery_capacity_max", type=float)

    conds = []
    if brand: conds.append(Vehicle.brand.ilike(f"%{brand}%"))
    if model: conds.append(Vehicle.model.ilike(f"%{model}%"))
    if year: conds.append(Vehicle.year == year)
    if year_min is not None: conds.append(Vehicle.year >= year_min)
    if year_max is not None: conds.append(Vehicle.year <= year_max)
    if km_min is not None: conds.append(Vehicle.km >= km_min)
    if km_max is not None: conds.append(Vehicle.km <= km_max)
    if price_min is not None: conds.append(Vehicle.price >= price_min)
    if price_max is not None: conds.append(Vehicle.price <= price_max)
    if condition: conds.append(Vehicle.condition == condition)
    if cap_min is not None: conds.append(Vehicle.battery_capacity_kwh >= cap_min)
    if cap_max is not None: conds.append(Vehicle.battery_capacity_kwh <= cap_max)

    q = Vehicle.query.filter(and_(*conds)) if conds else Vehicle.query
    return _paginate(q.order_by(Vehicle.created_at.desc()), _vehicle_json)


@bp.get("/batteries")
def search_batteries():
    brand = request.args.get("brand")
    cap_min = request.args.get("capacity_min", type=float)
    cap_max = request.args.get("capacity_max", type=float)
    price_min = request.args.get("price_min", type=int)
    price_max = request.args.get("price_max", type=int)
    health_min = request.args.get("health_min", type=float)
    health_max = request.args.get("health_max", type=float)
    cycles_min = request.args.get("cycles_min", type=int)
    cycles_max = request.args.get("cycles_max", type=int)
    year = request.args.get("year", type=int)
    year_min = request.args.get("year_min", type=int)
    year_max = request.args.get("year_max", type=int)

    conds = []
    if brand: conds.append(Battery.brand.ilike(f"%{brand}%"))
    if cap_min is not None: conds.append(Battery.capacity_kwh >= cap_min)
    if cap_max is not None: conds.append(Battery.capacity_kwh <= cap_max)
    if price_min is not None: conds.append(Battery.price >= price_min)
    if price_max is not None: conds.append(Battery.price <= price_max)
    if health_min is not None: conds.append(Battery.health_percent >= health_min)
    if health_max is not None: conds.append(Battery.health_percent <= health_max)
    if cycles_min is not None: conds.append(Battery.cycles >= cycles_min)
    if cycles_max is not None: conds.append(Battery.cycles <= cycles_max)
    if year: conds.append(Battery.year == year)
    if year_min is not None: conds.append(Battery.year >= year_min)
    if year_max is not None: conds.append(Battery.year <= year_max)

    q = Battery.query.filter(and_(*conds)) if conds else Battery.query
    return _paginate(q.order_by(Battery.created_at.desc()), _battery_json)


@bp.get("/vehicles/<int:vid>")
def get_vehicle(vid: int):
    v = Vehicle.query.get_or_404(vid)
    return _vehicle_json(v)


@bp.get("/batteries/<int:bid>")
def get_battery(bid: int):
    b = Battery.query.get_or_404(bid)
    return _battery_json(b)


@bp.post("/vehicles")
def create_vehicle():
    d = request.get_json(force=True)
    v = Vehicle(
        brand=d.get("brand"),
        model=d.get("model"),
        year=d.get("year"),
        km=d.get("km", 0),
        price=d.get("price", 0),
        condition=d.get("condition"),
        battery_capacity_kwh=d.get("battery_capacity_kwh"),
        seller_id=d.get("seller_id"),
    )
    db.session.add(v)
    db.session.commit()
    return {"id": v.id}, 201


@bp.post("/batteries")
def create_battery():
    d = request.get_json(force=True)
    b = Battery(
        brand=d.get("brand"),
        capacity_kwh=d.get("capacity_kwh"),
        cycles=d.get("cycles", 0),
        health_percent=d.get("health_percent", 100.0),
        price=d.get("price", 0),
        year=d.get("year"),
        condition=d.get("condition"),
        seller_id=d.get("seller_id"),
    )
    db.session.add(b)
    db.session.commit()
    return {"id": b.id}, 201
