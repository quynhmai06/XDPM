from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError
from models import db, User

register_bp = Blueprint("register_bp", __name__)

@register_bp.route("/register", methods=["GET", "POST"], endpoint="register")
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        if password != confirm:
            flash("Mật khẩu xác nhận không khớp", "error")
            return redirect(url_for("register_bp.register"))  

        if User.query.filter_by(username=username).first():
            flash("Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.", "error")
            return redirect(url_for("register_bp.register"))

        if User.query.filter_by(email=email).first():
            flash("Email đã được sử dụng. Vui lòng dùng email khác.", "error")
            return redirect(url_for("register_bp.register"))

        try:
            user = User(
                username=username,
                email=email,
                password=generate_password_hash(password),
                approved=False,
                is_admin=False,
            )
            db.session.add(user)
            db.session.commit()
            flash("Đăng ký thành công! Vui lòng chờ admin duyệt.", "success")
            return redirect(url_for("login_bp.login"))
        except IntegrityError:
            db.session.rollback()
            flash("Tên đăng nhập hoặc Email đã tồn tại.", "error")
            return redirect(url_for("register_bp.register"))

    return render_template("register.html")
