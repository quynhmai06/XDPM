import os
from flask import Flask, jsonify
from dotenv import load_dotenv
from db import db
from routes.users import bp_users
from routes.posts import bp_posts
from routes.transactions import bp_tx
from routes.config import bp_cfg
from routes.stats import bp_stats

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///admin.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    @app.get("/")
    def root():
        return jsonify(service="admin-service", status="ok")

    @app.get("/health")
    def health():
        return jsonify(service="admin-service", status="ok"), 200

    app.register_blueprint(bp_users)
    app.register_blueprint(bp_posts)
    app.register_blueprint(bp_tx)
    app.register_blueprint(bp_cfg)
    app.register_blueprint(bp_stats)
    return app


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.getenv("PORT", "5002"))
    app.run(host="0.0.0.0", port=port, debug=False)
