from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.drop_all()
    db.create_all()

    admin = User(
        username="admin",
        email="admin@example.com",
        password=generate_password_hash("12345"),
        is_admin=True,
        full_name="Administrator"
    )
    db.session.add(admin)
    db.session.commit()

    print("✅ Đã tạo tài khoản admin: username=admin, password=12345")
