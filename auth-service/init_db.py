# init_db.py
import os
from datetime import datetime
from sqlalchemy import or_
from werkzeug.security import generate_password_hash

# Import app + models dùng đúng config DB hiện tại
from app import app
from models import db, User, UserProfile

def reset_admin():
    with app.app_context():
        # Tạo bảng nếu chưa có
        db.create_all()

        # In ra DB đang dùng để bạn kiểm tra cho chắc
        print("SQLALCHEMY_DATABASE_URI =", app.config.get("SQLALCHEMY_DATABASE_URI"))

        # Xoá các bản ghi admin cũ (nếu có) theo username/email/role
        to_delete = User.query.filter(
            or_(
                User.role == "admin",
                User.username == "admin",
                User.email == "admin@example.com",
            )
        ).all()
        for u in to_delete:
            db.session.delete(u)
        db.session.commit()

        # Tạo admin mới (mật khẩu đã hash, cột name 'password' vẫn OK)
        admin = User(
            username="admin",
            email="admin@example.com",
            password=generate_password_hash("admin123"),  # cột 'password' lưu hash
            role="admin",
            approved=True,
            locked=False,
            created_at=datetime.utcnow(),
            phone="0123456789",
        )
        db.session.add(admin)
        db.session.commit()

        # Tạo hồ sơ rỗng 1-1 cho admin (nếu cần)
        prof = UserProfile(user_id=admin.id)
        db.session.add(prof)
        db.session.commit()

        print("✅ Admin user created:", admin.id, admin.username)

if __name__ == "__main__":
    reset_admin()
