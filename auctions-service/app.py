from flask import Flask, jsonify
from models import db, ensure_schema
from routes import bp
import os

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///auctions.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
app.register_blueprint(bp)

ensure_schema(app)

@app.get("/")
def root():
    return jsonify(service="auctions", status="ok", prefix="/auctions")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5006)), debug=True)
