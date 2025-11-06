from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import inspect, text

db = SQLAlchemy()

class Auction(db.Model):
    __tablename__ = "auctions"
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(20), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    seller_id = db.Column(db.Integer, nullable=False)
    starting_price = db.Column(db.Integer, nullable=False)
    min_increment = db.Column(db.Integer, default=1)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    buy_now_price = db.Column(db.Integer)
    ends_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="open")  # open|closed
    winner_id = db.Column(db.Integer)
    final_price = db.Column(db.Integer)
    closed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bid(db.Model):
    __tablename__ = "bids"
    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), index=True)
    bidder_id = db.Column(db.Integer, index=True)
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BuyerRequest(db.Model):
    __tablename__ = "buyer_requests"
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, nullable=False)
    desired_model = db.Column(db.String(120), nullable=False)
    desired_type = db.Column(db.String(20), default="car")
    max_price = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)
    deadline = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="open")  # open|awarded|expired|cancelled
    chosen_offer_id = db.Column(db.Integer, db.ForeignKey("seller_offers.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    chosen_offer = db.relationship("SellerOffer", foreign_keys=[chosen_offer_id], post_update=True)
    offers = db.relationship(
        "SellerOffer",
        back_populates="request",
        cascade="all, delete-orphan",
        foreign_keys="SellerOffer.request_id",
    )


class SellerOffer(db.Model):
    __tablename__ = "seller_offers"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("buyer_requests.id"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, nullable=False)
    offer_price = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text)
    status = db.Column(db.String(20), default="open")  # open|selected|rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    request = db.relationship(
        "BuyerRequest",
        back_populates="offers",
        foreign_keys=[request_id],
    )


def ensure_schema(app):
    with app.app_context():
        engine = db.engine
        insp = inspect(engine)
        if "auctions" in insp.get_table_names():
            cols = {col["name"] for col in insp.get_columns("auctions")}
            alterations = []
            if "min_increment" not in cols:
                alterations.append("ADD COLUMN min_increment INTEGER DEFAULT 1")
            if "start_time" not in cols:
                alterations.append("ADD COLUMN start_time DATETIME")
            if "winner_id" not in cols:
                alterations.append("ADD COLUMN winner_id INTEGER")
            if "final_price" not in cols:
                alterations.append("ADD COLUMN final_price INTEGER")
            if "closed_at" not in cols:
                alterations.append("ADD COLUMN closed_at DATETIME")
            if alterations:
                with engine.begin() as conn:
                    for clause in alterations:
                        try:
                            conn.execute(text(f"ALTER TABLE auctions {clause}"))
                        except Exception:
                            pass
        if "buyer_requests" in insp.get_table_names():
            cols = {col["name"] for col in insp.get_columns("buyer_requests")}
            if "desired_type" not in cols:
                with engine.begin() as conn:
                    try:
                        conn.execute(text("ALTER TABLE buyer_requests ADD COLUMN desired_type VARCHAR(20) DEFAULT 'car'"))
                    except Exception:
                        pass
        db.create_all()
