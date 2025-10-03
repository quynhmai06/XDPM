from flask import Flask, render_template, redirect, url_for, session, flash
from models import db
from register import register_bp
from login import login_bp
from admin import admin_bp

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ev_trading.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "dev"

db.init_app(app)
app.register_blueprint(register_bp)
app.register_blueprint(login_bp)
app.register_blueprint(admin_bp)

@app.route("/", endpoint="home")
def home():
    return render_template("index.html")

@app.route("/admin", endpoint="admin_dashboard")
def admin_dashboard():
    return render_template("admin.html")

@app.route("/logout", endpoint="logout")
def logout_all():
    was_admin = session.get("is_admin")
    session.clear()
    flash("Đã đăng xuất!", "success")
    return redirect(url_for("admin.admin_dashboard") if was_admin else url_for("home"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
