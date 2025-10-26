# init_db.py
import os
from datetime import datetime
from sqlalchemy import or_
from werkzeug.security import generate_password_hash
from app import app
from models import db, User, UserProfile

def reset_admin():
    with app.app_context():
        db.create_all()

        print("SQLALCHEMY_DATABASE_URI =", app.config.get("SQLALCHEMY_DATABASE_URI"))

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

        admin = User(
            username="admin",
            email="admin@example.com",
            password=generate_password_hash("admin123"), 
            role="admin",
            approved=True,
            locked=False,
            created_at=datetime.utcnow(),
            phone="0123456789",
        )
        db.session.add(admin)
        db.session.commit()

        prof = UserProfile(user_id=admin.id)
        db.session.add(prof)
        db.session.commit()

        print("✅ Admin user created:", admin.id, admin.username)

if __name__ == "__main__":
    reset_admin()
