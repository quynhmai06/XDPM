
from flask import Blueprint, request
from datetime import datetime
from models import db, Auction, Bid

bp = Blueprint("auctions", __name__, url_prefix="/auctions")


@bp.get("/")
def health():
    return {"service": "auctions", "status": "ok"}


@bp.post("")
def create_auction():
    d = request.get_json(force=True)
    a = Auction(
        item_type=d.get("item_type"),
        item_id=d.get("item_id"),
        seller_id=d.get("seller_id"),
        starting_price=d.get("starting_price"),
        buy_now_price=d.get("buy_now_price"),
        ends_at=datetime.fromisoformat(d.get("ends_at")),
        status="open",
    )
    db.session.add(a)
    db.session.commit()
    return {"id": a.id}, 201


@bp.post("/<int:auction_id>/bid")
def place_bid(auction_id: int):
    a = Auction.query.get_or_404(auction_id)
    if a.status != "open":
        return {"error": "closed"}, 400
    d = request.get_json(force=True)
    amount = int(d.get("amount", 0))
    bidder_id = d.get("bidder_id")
    if amount <= 0 or not bidder_id:
        return {"error": "invalid"}, 400
    last = Bid.query.filter_by(auction_id=auction_id).order_by(Bid.amount.desc()).first()
    min_amount = last.amount if last else a.starting_price
    if amount <= min_amount:
        return {"error": "low_bid", "min": min_amount + 1}, 400
    b = Bid(auction_id=auction_id, bidder_id=bidder_id, amount=amount)
    db.session.add(b)
    db.session.commit()
    return {"id": b.id, "amount": b.amount}


@bp.post("/<int:auction_id>/buy-now")
def buy_now(auction_id: int):
    a = Auction.query.get_or_404(auction_id)
    if a.status != "open" or not a.buy_now_price:
        return {"error": "not_available"}, 400
    a.status = "closed"
    db.session.commit()
    return {"ok": True, "price": a.buy_now_price}


@bp.get("/active")
def list_active():
    now = datetime.utcnow()
    auctions = Auction.query.filter(Auction.status == "open", Auction.ends_at > now).order_by(Auction.ends_at.asc()).all()
    return {"data": [{
        "id": a.id,
        "item_type": a.item_type,
        "item_id": a.item_id,
        "starting_price": a.starting_price,
        "buy_now_price": a.buy_now_price,
        "ends_at": a.ends_at.isoformat(),
    } for a in auctions]}
