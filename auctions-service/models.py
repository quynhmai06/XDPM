from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Auction(db.Model):
    __tablename__ = "auctions"
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(20), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    seller_id = db.Column(db.Integer, nullable=False)
    starting_price = db.Column(db.Integer, nullable=False)
    buy_now_price = db.Column(db.Integer)
    ends_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="open")  # open|closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bid(db.Model):
    __tablename__ = "bids"
    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), index=True)
    bidder_id = db.Column(db.Integer, index=True)
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)