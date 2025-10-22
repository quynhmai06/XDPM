# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class UserProfile(db.Model):
    __tablename__ = "user_profile"

    id = db.Column(db.Integer, primary_key=True)

    # FK 1-1 tới users.id
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Thông tin hồ sơ
    full_name   = db.Column(db.String(120))
    address     = db.Column(db.String(255))
    gender      = db.Column(db.String(20))
    birthdate   = db.Column(db.Date, nullable=True)         # hoặc đổi sang String nếu bạn muốn
    avatar_url  = db.Column(db.String(255))

    # Bổ sung vì to_dict() đang dùng
    vehicle_info = db.Column(db.String(255))
    battery_info = db.Column(db.String(255))

    # Thời gian cập nhật (tự cập nhật khi commit)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Quan hệ về User: dùng back_populates để không xung đột với User.profile
    user = db.relationship("User", back_populates="profile")

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "full_name": self.full_name,
            "address": self.address,
            "vehicle_info": self.vehicle_info,
            "battery_info": self.battery_info,
            "avatar_url": self.avatar_url,
            "gender": self.gender,
            "birthdate": self.birthdate.isoformat() if self.birthdate else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

# === User (giữ nguyên, chỉ cần chắc chắn có back_populates như dưới) ===
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="member")
    approved = db.Column(db.Boolean, default=False)
    locked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    phone = db.Column(db.String(20), unique=True)

    profile = db.relationship("UserProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")

    def to_dict_basic(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }
