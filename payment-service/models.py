# models.py
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Enum, Index
from db import db

# ---- Payment method: thêm CASH
class PaymentMethod(PyEnum):
    E_WALLET = "e-wallet"
    BANKING  = "banking"
    CASH     = "cash"          # <— thêm

# ---- Payment status: bỏ REVIEW
class PaymentStatus(PyEnum):
    PENDING  = "pending"
    PAID     = "paid"
    FAILED   = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"

class Payment(db.Model):
    __tablename__ = "payments"

    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, nullable=False, index=True)
    buyer_id   = db.Column(db.Integer, nullable=False, index=True)
    seller_id  = db.Column(db.Integer, nullable=False, index=True)
    amount     = db.Column(db.Integer, nullable=False)  # VND integer

    # enum đã đặt tên rõ ràng để tiện migrate
    method     = db.Column(
        Enum(PaymentMethod, name="payment_method"),
        nullable=False,
        default=PaymentMethod.E_WALLET
    )

    # đổi provider mặc định sang ZaloPay
    provider   = db.Column(db.String(50), nullable=False, default="ZaloPay")

    status     = db.Column(
        Enum(PaymentStatus, name="payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_payment_status_created", "status", "created_at"),
    )

class Contract(db.Model):
    __tablename__ = "contracts"
    id            = db.Column(db.Integer, primary_key=True)
    payment_id    = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False, index=True)
    title         = db.Column(db.String(200), nullable=False)
    content       = db.Column(db.Text, nullable=False)  # nội dung hợp đồng (plain text/HTML)
    signer_name   = db.Column(db.String(120))
    signed_at     = db.Column(db.DateTime)
    signature_jwt = db.Column(db.Text)                  # chữ ký số dạng JWT
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    payment = db.relationship("Payment", backref="contract", uselist=False)

