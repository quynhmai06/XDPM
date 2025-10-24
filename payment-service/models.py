# models.py (REPLACE TOÀN BỘ NỘI DUNG)
from datetime import datetime
from db import db

class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    buyer_id = db.Column(db.Integer, nullable=False)
    seller_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # VND integer
    method = db.Column(db.String(50), default="e-wallet")   # e-wallet | banking
    provider = db.Column(db.String(50), default="DemoPay")  # MoMo, ZaloPay, VNPAY...
    status = db.Column(db.String(20), default="pending")    # pending | paid | failed | canceled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Contract(db.Model):
    __tablename__ = "contracts"
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # nội dung hợp đồng (plain text/HTML)
    signer_name = db.Column(db.String(120))
    signed_at = db.Column(db.DateTime)
    signature_jwt = db.Column(db.Text)           # chữ ký số dạng JWT
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    payment = db.relationship("Payment", backref="contract", uselist=False)
