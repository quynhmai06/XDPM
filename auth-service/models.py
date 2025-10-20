# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# === ADD: UserProfile (đặt trước User) ===
class UserProfile(db.Model):
    __tablename__ = "user_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    full_name    = db.Column(db.String(255))
    address      = db.Column(db.String(500))
    vehicle_info = db.Column(db.Text)            # JSON text
    battery_info = db.Column(db.Text)            # JSON text
    avatar_url   = db.Column(db.String(500))
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship("User", back_populates="profile")
    gender     = db.Column(db.String(10))        # "male" | "female" | "other"
    birthdate  = db.Column(db.Date, nullable=True)

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
