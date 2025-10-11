# init_db.py
from werkzeug.security import generate_password_hash
from sqlalchemy import text
from app import app, db
from models import User

def ensure_schema():
    """Tạo bảng nếu chưa có và bổ sung cột 'phone' nếu bảng đã tồn tại mà thiếu cột"""
    with app.app_context():
        db.create_all()
        engine = db.engine
        driver = engine.url.drivername

        if driver.startswith("sqlite"):
            with engine.connect() as conn:   # ✅ mở connection đúng cách
                cols = [r[1] for r in conn.execute(text("PRAGMA table_info(users);")).fetchall()]
                if "phone" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(20)"))
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone ON users(phone)"))
                    print("[migrate] Added users.phone (SQLite)")
        else:
            with engine.connect() as conn:
                exists = conn.execute(text("""
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'phone'
                    LIMIT 1
                """)).fetchone()
                if not exists:
                    if driver.startswith("postgres"):
                        conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(20) UNIQUE"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(20)"))
                        try:
                            conn.execute(text("CREATE UNIQUE INDEX uq_users_phone ON users(phone)"))
                        except Exception:
                            pass
                    print("[migrate] Added users.phone (non-SQLite)")

def seed_admin():
    """Tạo tài khoản admin nếu chưa có"""
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            u = User(
                username="admin",
                email="admin@example.com",
                password=generate_password_hash("Admin@123"),
                role="admin",
                approved=True,
                locked=False,
                phone=None,  # có thể để None
            )
            db.session.add(u)
            db.session.commit()
            print("[seed] Admin user created: admin / Admin@123")
        else:
            print("[seed] Admin user already exists")

if __name__ == "__main__":
    print(f"[info] DB URL: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    ensure_schema()
    seed_admin()
    print("[done] init_db finished.")
