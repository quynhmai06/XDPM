from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Transaction(db.Model):
    """Bảng giao dịch chính - lưu mọi giao dịch trên hệ thống"""
    __tablename__ = "transactions"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Thông tin cơ bản
    transaction_code = db.Column(db.String(50), unique=True, nullable=False, index=True)  # Mã GD duy nhất
    transaction_type = db.Column(db.String(50), nullable=False, index=True)  
    # Loại: order_purchase, order_sale, wallet_deposit, wallet_withdraw, refund, platform_fee, escrow_release
    
    # Người liên quan
    user_id = db.Column(db.Integer, index=True, nullable=False)  # Người thực hiện GD
    partner_id = db.Column(db.Integer, index=True)  # Đối tác (người mua/bán)
    
    # Thông tin đơn hàng liên quan
    order_id = db.Column(db.Integer, index=True)  # ID đơn hàng nếu có
    item_type = db.Column(db.String(20))  # vehicle, battery
    item_id = db.Column(db.Integer)
    item_name = db.Column(db.String(200))  # Snapshot tên sản phẩm
    item_image = db.Column(db.String(500))  # URL ảnh sản phẩm
    
    # Thông tin tiền
    amount = db.Column(db.Integer, nullable=False)  # Số tiền chính (VND)
    fee = db.Column(db.Integer, default=0)  # Phí (nếu có)
    net_amount = db.Column(db.Integer, nullable=False)  # Số tiền thực nhận/trả
    
    # Phương thức và trạng thái
    payment_method = db.Column(db.String(50))  # momo, bank_transfer, wallet, cod
    status = db.Column(db.String(50), default="pending", index=True)  
    # pending, processing, completed, refunded, cancelled, failed
    
    # Ghi chú và metadata
    description = db.Column(db.Text)
    extra_data = db.Column(db.JSON)  # Lưu thông tin thêm (renamed from metadata to avoid SQLAlchemy conflict)
    
    # Thời gian
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)  # Thời gian hoàn tất


class TransactionEvent(db.Model):
    """Timeline sự kiện của giao dịch"""
    __tablename__ = "transaction_events"
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False, index=True)
    
    event_type = db.Column(db.String(50), nullable=False)  
    # created, payment_received, processing, shipped, completed, refunded, cancelled
    
    actor_type = db.Column(db.String(20))  # system, user, admin
    actor_id = db.Column(db.Integer)  # ID người thực hiện (nếu là user/admin)
    
    description = db.Column(db.Text)
    extra_data = db.Column(db.JSON)  # Renamed from metadata
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WalletTransaction(db.Model):
    """Giao dịch ví điện tử riêng - chi tiết hơn"""
    __tablename__ = "wallet_transactions"
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), index=True)
    
    user_id = db.Column(db.Integer, nullable=False, index=True)
    wallet_type = db.Column(db.String(20), default="main")  # main, escrow, commission
    
    transaction_type = db.Column(db.String(50), nullable=False)  
    # deposit, withdraw, refund, platform_fee, escrow_hold, escrow_release, commission_earn
    
    amount = db.Column(db.Integer, nullable=False)  # Số tiền biến động
    balance_before = db.Column(db.Integer, nullable=False)  # Số dư trước
    balance_after = db.Column(db.Integer, nullable=False)  # Số dư sau
    
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="completed")  # pending, completed, failed
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
