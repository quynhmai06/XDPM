from werkzeug.security import generate_password_hash
from sqlalchemy import or_
from app import app, db
from models import User

def reset_admin():
    with app.app_context():
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

        new_admin = User(
            username="admin",
            email="admin@example.com",
            password=generate_password_hash("123"),
            role="admin",
            approved=True,
            locked=False,
            phone=None,
        )
        db.session.add(new_admin)
        db.session.commit()
        print("[seed] Admin account created: admin / 123")

if __name__ == "__main__":
    reset_admin()
