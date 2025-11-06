import os
from flask import Flask, jsonify
from models import db
from routes import bp

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "auth.db")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.getenv("SECRET_KEY", os.getenv("JWT_SECRET", "devsecret"))

db.init_app(app)
app.register_blueprint(bp)

@app.get("/")
def root():
    return jsonify(service="auth", status="ok", prefix="/auth")

@app.get("/health")
def health():
    return jsonify(ok=True), 200

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5001)), debug=True)
