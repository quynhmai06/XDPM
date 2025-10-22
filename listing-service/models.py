from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Product(db.Model):
    __tablename__ = "products"

    id               = db.Column(db.Integer, primary_key=True)
    product_type     = db.Column(db.String(20), nullable=False, default="car", index=True)
    name             = db.Column(db.String(180), nullable=False, index=True)
    description      = db.Column(db.Text)
    price            = db.Column(db.Integer, nullable=False, default=0, index=True)
    brand            = db.Column(db.String(80), index=True)
    province         = db.Column(db.String(80), index=True)
    year             = db.Column(db.Integer, index=True)
    mileage          = db.Column(db.Integer)
    battery_capacity = db.Column(db.String(50))
    owner            = db.Column(db.String(80), nullable=False, index=True)

    main_image_url   = db.Column(db.String(255))
    sub_image_urls   = db.Column(db.Text)  # JSON list string

    approved         = db.Column(db.Boolean, default=False, index=True)
    approved_at      = db.Column(db.DateTime)
    approved_by      = db.Column(db.String(80))

    created_at       = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
