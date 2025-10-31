#!/usr/bin/env python3
"""
Script tạo user admin để test admin-service endpoints
Chạy: docker-compose exec auth_service python create_admin.py
"""
import os
import sys
from werkzeug.security import generate_password_hash

# Thiết lập path để import models
sys.path.insert(0, os.path.dirname(__file__))

from models import db, User
from app import app

def create_admin(username="admin", email="admin@xdpm.local", password="admin123"):
    with app.app_context():
        # Kiểm tra admin đã tồn tại chưa
        existing = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing:
            print(f"⚠️  User '{username}' đã tồn tại (ID: {existing.id})")
            if existing.role != "admin":
                existing.role = "admin"
                existing.approved = True
                existing.locked = False
                db.session.commit()
                print(f"✅ Đã cập nhật role thành 'admin'")
            else:
                print(f"✅ User đã là admin")
            return existing
        
        # Tạo admin mới
        admin = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            role="admin",
            approved=True,
            locked=False
        )
        db.session.add(admin)
        db.session.commit()
        
        print(f"""
✅ Tạo admin thành công!

👤 Username: {username}
📧 Email:    {email}
🔑 Password: {password}
🆔 User ID:  {admin.id}

📝 Để lấy JWT token, chạy:
curl -X POST http://localhost:5001/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{{"username":"{username}","password":"{password}"}}'
""")
        return admin

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Tạo user admin')
    parser.add_argument('--username', default='admin', help='Username (mặc định: admin)')
    parser.add_argument('--email', default='admin@xdpm.local', help='Email')
    parser.add_argument('--password', default='admin123', help='Password (mặc định: admin123)')
    
    args = parser.parse_args()
    create_admin(args.username, args.email, args.password)
