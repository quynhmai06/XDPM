from flask import Flask, jsonify
from models import db, User
from routes import bp
import os
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///auth.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Khởi tạo DB + đăng ký blueprint
db.init_app(app)
app.register_blueprint(bp)            # nếu bp CHƯA có url_prefix, bạn có thể dùng: app.register_blueprint(bp, url_prefix="/auth")

# (tuỳ chọn) Health check để vào http://127.0.0.1:5001/ không bị 404
@app.get("/")
def root():
    return jsonify(service="auth", status="ok", prefix="/auth")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # seed admin mặc định
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
            print("✅ Đã tạo admin mặc định: username=admin, password=12345")

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5001)), debug=True)
