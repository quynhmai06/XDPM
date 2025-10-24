import os
from flask import Flask, jsonify
from db import db
from routes import bp as payment_bp

# ---- Factory (đơn giản) ----
def create_app():
    app = Flask(__name__)

    # Lấy chuỗi kết nối từ docker-compose: postgresql+psycopg2://ev:evpass@db:5432/evdb
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///payment.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_AS_ASCII"] = False

    db.init_app(app)

    # Tạo bảng lần đầu (an toàn khi chạy nhiều lần)
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            # Không crash service nếu migration/bảng đã tồn tại
            print("[payment-service] create_all warning:", e)

    # Đăng ký blueprint
    app.register_blueprint(payment_bp)

    # Health-check nhanh
    @app.get("/")
    def _root():
        return jsonify({"service": "payment_service", "status": "ok"})

    return app


app = create_app()

if __name__ == "__main__":
    # Chạy dev server khi chạy trực tiếp (trong docker bạn dùng gunicorn/werkzeug tùy ý)
    app.run(host="0.0.0.0", port=5003, debug=True)
