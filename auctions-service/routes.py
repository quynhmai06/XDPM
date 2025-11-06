import os
import requests
from flask import Blueprint, request
from datetime import datetime, timezone
from models import db, Auction, Bid, BuyerRequest, SellerOffer
from sqlalchemy import func

bp = Blueprint("auctions", __name__, url_prefix="/auctions")

ORDERS_URL = os.getenv("ORDERS_URL", "http://orders_service:5005")


def _now() -> datetime:
    return datetime.utcnow()


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def _create_order(buyer_id: int, seller_id: int, item_type: str, item_id: int, price: int) -> None:
    if not buyer_id or not seller_id or not price:
        return
    payload = {
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "item_type": item_type,
        "item_id": item_id,
        "price": price,
    }
    try:
        requests.post(f"{ORDERS_URL}/orders", json=payload, timeout=5)
    except requests.RequestException:
        pass


def _finalize_auction(a: Auction, winner_id: int | None = None, final_price: int | None = None) -> dict:
    if a.status != "open":
        return {"status": a.status}
    top_bid = (
        Bid.query.filter_by(auction_id=a.id)
        .order_by(Bid.amount.desc())
        .first()
    )
    win_id = None
    win_amount = None
    if winner_id and final_price:
        win_id = winner_id
        win_amount = final_price
    elif top_bid:
        win_id = top_bid.bidder_id
        win_amount = top_bid.amount
    a.status = "closed"
    a.closed_at = _now()
    if win_id:
        a.winner_id = win_id
        a.final_price = win_amount
        db.session.add(a)
        db.session.commit()
        _create_order(win_id, a.seller_id, a.item_type, a.item_id, win_amount or a.starting_price)
    else:
        a.winner_id = None
        a.final_price = a.starting_price
        db.session.add(a)
        db.session.commit()
    return {
        "status": a.status,
        "winner_id": a.winner_id,
        "final_price": a.final_price,
    }


def _close_expired_auctions():
    now = _now()
    expired = (
        Auction.query
        .filter(Auction.status == "open", Auction.ends_at <= now)
        .all()
    )
    for a in expired:
        _finalize_auction(a)


def _expire_requests():
    now = _now()
    requests_q = (
        BuyerRequest.query
        .filter(BuyerRequest.status == "open", BuyerRequest.deadline <= now)
        .all()
    )
    for req in requests_q:
        req.status = "expired"
    if requests_q:
        db.session.commit()


@bp.get("/")
def health():
    return {"service": "auctions", "status": "ok"}


@bp.post("")
def create_auction():
    d = request.get_json(force=True)
    start_price = d.get("start_price", d.get("starting_price"))
    min_inc = d.get("min_increment") or 1
    ends_at = _parse_dt(d.get("end_time") or d.get("ends_at"))
    start_time = _parse_dt(d.get("start_time")) or _now()
    if not all([d.get("item_type"), d.get("item_id"), d.get("seller_id"), start_price, ends_at]):
        return {"error": "missing_fields"}, 400
    if ends_at <= start_time:
        return {"error": "invalid_time_range"}, 400
    a = Auction(
        item_type=d.get("item_type"),
        item_id=d.get("item_id"),
        seller_id=d.get("seller_id"),
        starting_price=int(start_price),
        min_increment=int(min_inc),
        buy_now_price=d.get("buy_now_price"),
        start_time=start_time,
        ends_at=ends_at,
        status="open",
    )
    db.session.add(a)
    db.session.commit()
    return {"id": a.id}, 201


@bp.post("/<int:auction_id>/bid")
def place_bid(auction_id: int):
    a = Auction.query.get_or_404(auction_id)
    now = _now()
    if a.status != "open" or (a.start_time and now < a.start_time):
        return {"error": "not_open"}, 400
    if now >= a.ends_at:
        _finalize_auction(a)
        return {"error": "closed"}, 400
    d = request.get_json(force=True)
    amount = int(d.get("amount", 0))
    bidder_id = d.get("bidder_id")
    if amount <= 0 or not bidder_id:
        return {"error": "invalid"}, 400
    last = Bid.query.filter_by(auction_id=auction_id).order_by(Bid.amount.desc()).first()
    baseline = last.amount if last else a.starting_price
    min_amount = baseline + (a.min_increment or 1)
    if amount < min_amount:
        return {"error": "low_bid", "min": min_amount}, 400
    b = Bid(auction_id=auction_id, bidder_id=bidder_id, amount=amount)
    db.session.add(b)
    db.session.commit()
    return {"id": b.id, "amount": b.amount}


@bp.post("/<int:auction_id>/buy-now")
def buy_now(auction_id: int):
    a = Auction.query.get_or_404(auction_id)
    if a.status != "open" or not a.buy_now_price:
        return {"error": "not_available"}, 400
    payload = request.get_json(silent=True) or {}
    buyer_id = payload.get("buyer_id")
    result = _finalize_auction(a, winner_id=buyer_id, final_price=a.buy_now_price)
    result.update({
        "ok": True,
        "item_type": a.item_type,
        "item_id": a.item_id,
        "seller_id": a.seller_id,
        "auction_id": a.id,
        "final_price": a.final_price,
    })
    return result


@bp.post("/<int:auction_id>/close")
def close_auction(auction_id: int):
    a = Auction.query.get_or_404(auction_id)
    if a.status != "open":
        return {"error": "already_closed"}, 400
    d = request.get_json(force=True)
    requester = d.get("seller_id")
    if requester != a.seller_id:
        return {"error": "forbidden"}, 403
    result = _finalize_auction(a)
    return result


@bp.get("/active")
def list_active():
    _close_expired_auctions()
    now = _now()
    auctions = (
        Auction.query
        .filter(Auction.status == "open", Auction.ends_at > now)
        .order_by(Auction.ends_at.asc())
        .all()
    )
    data = []
    for a in auctions:
        highest = db.session.query(func.max(Bid.amount)).filter(Bid.auction_id == a.id).scalar()
        data.append({
            "id": a.id,
            "item_type": a.item_type,
            "item_id": a.item_id,
            "starting_price": a.starting_price,
            "min_increment": a.min_increment,
            "highest_bid": int(highest) if highest is not None else None,
            "buy_now_price": a.buy_now_price,
            "start_time": a.start_time.isoformat() if a.start_time else None,
            "ends_at": a.ends_at.isoformat(),
        })
    return {"data": data}


@bp.get("/<int:auction_id>")
def get_auction_detail(auction_id: int):
    a = Auction.query.get_or_404(auction_id)
    bid_count = Bid.query.filter_by(auction_id=auction_id).count()
    highest = db.session.query(func.max(Bid.amount)).filter(Bid.auction_id == auction_id).scalar()
    return {
        "id": a.id,
        "item_type": a.item_type,
        "item_id": a.item_id,
        "seller_id": a.seller_id,
        "starting_price": a.starting_price,
        "min_increment": a.min_increment,
        "buy_now_price": a.buy_now_price,
        "highest_bid": int(highest) if highest is not None else None,
        "final_price": a.final_price,
        "winner_id": a.winner_id,
        "start_time": a.start_time.isoformat() if a.start_time else None,
        "ends_at": a.ends_at.isoformat(),
        "status": a.status,
        "created_at": a.created_at.isoformat(),
        "closed_at": a.closed_at.isoformat() if a.closed_at else None,
        "bid_count": bid_count,
    }


@bp.get("/<int:auction_id>/bids")
def get_auction_bids(auction_id: int):
    Auction.query.get_or_404(auction_id)
    bids = (
        Bid.query
        .filter_by(auction_id=auction_id)
        .order_by(Bid.created_at.desc())
        .all()
    )
    data = []
    for b in bids:
        data.append({
            "id": b.id,
            "bidder_id": b.bidder_id,
            "amount": b.amount,
            "created_at": b.created_at.isoformat(),
        })
    return {"data": data}


@bp.post("/buyer-requests")
def create_buyer_request():
    d = request.get_json(force=True)
    deadline = _parse_dt(d.get("deadline"))
    if not deadline or deadline <= _now():
        return {"error": "invalid_deadline"}, 400
    requester_id = d.get("requester_id")
    desired_model = (d.get("desired_model") or "").strip()
    max_price = d.get("max_price")
    if not requester_id or not desired_model or max_price is None:
        return {"error": "missing_fields"}, 400
    desired_type = (d.get("desired_type") or "car").lower()
    if desired_type not in {"car", "battery"}:
        desired_type = "car"
    try:
        max_price_val = int(max_price)
    except (TypeError, ValueError):
        return {"error": "invalid_price"}, 400
    if max_price_val <= 0:
        return {"error": "invalid_price"}, 400
    req = BuyerRequest(
        requester_id=requester_id,
        desired_model=desired_model,
        desired_type=desired_type,
        max_price=max_price_val,
        notes=(d.get("notes") or "").strip() or None,
        deadline=deadline,
    )
    db.session.add(req)
    db.session.commit()
    return {"id": req.id}, 201


@bp.get("/buyer-requests/active")
def list_active_buyer_requests():
    _expire_requests()
    now = _now()
    qs = (
        BuyerRequest.query
        .filter(BuyerRequest.status == "open", BuyerRequest.deadline > now)
        .order_by(BuyerRequest.deadline.asc())
        .all()
    )
    data = []
    for req in qs:
        offers = [
            {
                "id": off.id,
                "seller_id": off.seller_id,
                "offer_price": off.offer_price,
                "note": off.note,
                "status": off.status,
                "created_at": off.created_at.isoformat(),
            }
            for off in req.offers
        ]
        data.append({
            "id": req.id,
            "desired_model": req.desired_model,
            "desired_type": req.desired_type,
            "max_price": req.max_price,
            "deadline": req.deadline.isoformat(),
            "requester_id": req.requester_id,
            "notes": req.notes,
            "offers": offers,
        })
    return {"data": data}


@bp.post("/buyer-requests/<int:request_id>/offers")
def submit_seller_offer(request_id: int):
    req = BuyerRequest.query.get_or_404(request_id)
    if req.status != "open" or req.deadline <= _now():
        return {"error": "request_closed"}, 400
    d = request.get_json(force=True)
    seller_id = d.get("seller_id")
    offer_price = d.get("offer_price")
    if not seller_id or offer_price is None:
        return {"error": "missing_fields"}, 400
    offer_price = int(offer_price)
    if offer_price <= 0 or offer_price > req.max_price:
        return {"error": "invalid_price", "max": req.max_price}, 400
    offer = SellerOffer(
        request_id=req.id,
        seller_id=seller_id,
        offer_price=offer_price,
        note=(d.get("note") or "").strip() or None,
    )
    db.session.add(offer)
    db.session.commit()
    return {"id": offer.id}, 201


@bp.post("/buyer-requests/<int:request_id>/select")
def select_seller_offer(request_id: int):
    req = BuyerRequest.query.get_or_404(request_id)
    if req.status != "open":
        return {"error": "request_not_open"}, 400
    d = request.get_json(force=True)
    buyer_id = d.get("buyer_id")
    offer_id = d.get("offer_id")
    if buyer_id != req.requester_id:
        return {"error": "forbidden"}, 403
    offer = SellerOffer.query.filter_by(id=offer_id, request_id=request_id).first()
    if not offer:
        return {"error": "offer_not_found"}, 404
    req.status = "awarded"
    req.chosen_offer_id = offer.id
    offer.status = "selected"
    other_offers = SellerOffer.query.filter(
        SellerOffer.request_id == request_id,
        SellerOffer.id != offer.id,
    )
    for other in other_offers:
        other.status = "rejected"
    db.session.commit()
    _create_order(buyer_id, offer.seller_id, req.desired_type or d.get("item_type", "car"), d.get("item_id", request_id), offer.offer_price)
    return {
        "ok": True,
        "request_id": req.id,
        "offer_id": offer.id,
        "seller_id": offer.seller_id,
        "price": offer.offer_price,
    }


@bp.get("/buyer-requests/<int:request_id>/offers")
def list_request_offers(request_id: int):
    req = BuyerRequest.query.get_or_404(request_id)
    offers = (
        SellerOffer.query
        .filter_by(request_id=req.id)
        .order_by(SellerOffer.offer_price.asc())
        .all()
    )
    data = [
        {
            "id": off.id,
            "seller_id": off.seller_id,
            "offer_price": off.offer_price,
            "note": off.note,
            "status": off.status,
            "created_at": off.created_at.isoformat(),
        }
        for off in offers
    ]
    return {
        "request": {
            "id": req.id,
            "desired_model": req.desired_model,
        "desired_type": req.desired_type,
            "max_price": req.max_price,
            "deadline": req.deadline.isoformat(),
            "status": req.status,
            "requester_id": req.requester_id,
        },
        "offers": data,
    }
