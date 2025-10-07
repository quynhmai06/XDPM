# init_db.py
from models import db, User
from werkzeug.security import generate_password_hash
from app import app

with app.app_context():
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
        print("✅ Seed admin (1 lần)")
    else:
        print("ℹ️ Admin đã tồn tại, bỏ qua.")
