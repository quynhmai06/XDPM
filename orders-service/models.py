from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, index=True, nullable=False)
    seller_id = db.Column(db.Integer, index=True, nullable=False)
    item_type = db.Column(db.String(20), nullable=False)  # vehicle|battery
    item_id = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="created")  # created, paid, shipped, done, canceled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
