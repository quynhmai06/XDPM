from datetime import datetime
from db import db

# Lưu quyết định kiểm duyệt/cấu hình/khieu nại bên phía admin-service (metadata)
class ModerationLog(db.Model):
    __tablename__ = "moderation_logs"
    id = db.Column(db.Integer, primary_key=True)
    target_type = db.Column(db.String(32), nullable=False)  # 'user' | 'post' | 'transaction'
    target_id = db.Column(db.String(64), nullable=False)    # id bên service khác
    action = db.Column(db.String(32), nullable=False)       # 'approve' | 'lock' | 'mark_verified' | 'flag_spam' | ...
    reason = db.Column(db.Text)
    admin_username = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FeeConfig(db.Model):
    __tablename__ = "fee_configs"
    id = db.Column(db.Integer, primary_key=True)
    # phần trăm phí theo loại giao dịch/tin đăng
    tx_fee_pct = db.Column(db.Float, default=1.5)           # %
    seller_commission_pct = db.Column(db.Float, default=2)  # %
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Complaint(db.Model):
    __tablename__ = "complaints"
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(64), nullable=False)
    reporter = db.Column(db.String(80), nullable=False)  # username/email người báo cáo
    status = db.Column(db.String(20), default="open")    # open | reviewing | resolved | rejected
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
