from models import db, User
from werkzeug.security import generate_password_hash
from app import app

with app.app_context():
    print("🔄 Đang khởi tạo cơ sở dữ liệu...")
    db.drop_all()
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            email="admin@example.com",
            password=generate_password_hash("12345"),
            role="admin",
            approved=True
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Đã tạo tài khoản admin: admin / 12345")
    else:
        print("ℹ️ Tài khoản admin đã tồn tại, bỏ qua seed.")
