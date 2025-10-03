from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password   = db.Column(db.String(128), nullable=False)   # lưu password hash
    email      = db.Column(db.String(120), unique=True, nullable=False, index=True)
    
    is_admin   = db.Column(db.Boolean, default=False)        # True = quản trị viên
    approved   = db.Column(db.Boolean, default=False)        # True = được admin duyệt

    full_name  = db.Column(db.String(120))
    phone      = db.Column(db.String(20))
    birthdate  = db.Column(db.Date)
    address    = db.Column(db.String(255))
    gender     = db.Column(db.String(10))                    # Nam / Nữ / Khác
    avatar     = db.Column(db.String(255))                   # đường dẫn ảnh đại diện
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username} {'(Admin)' if self.is_admin else ''}>"
