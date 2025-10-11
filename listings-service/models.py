from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Vehicle(db.Model):
    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(120), index=True)
    model = db.Column(db.String(120), index=True)
    year = db.Column(db.Integer, index=True)
    km = db.Column(db.Integer, index=True)
    price = db.Column(db.Integer, index=True)
    condition = db.Column(db.String(50), index=True)  # new, used, good, fair
    battery_capacity_kwh = db.Column(db.Float, index=True)
    seller_id = db.Column(db.Integer, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Battery(db.Model):
    __tablename__ = "batteries"
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(120), index=True)
    capacity_kwh = db.Column(db.Float, index=True)
    cycles = db.Column(db.Integer, index=True)
    health_percent = db.Column(db.Float, index=True)
    price = db.Column(db.Integer, index=True)
    year = db.Column(db.Integer, index=True)
    condition = db.Column(db.String(50), index=True)
    seller_id = db.Column(db.Integer, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)