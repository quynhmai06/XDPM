from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from models import db, User

login_bp = Blueprint("login_bp", __name__)

@login_bp.route("/login", methods=["GET", "POST"], endpoint="login")  
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        user = User.query.filter_by(username=username).first()

        if not user:
            flash("Tài khoản không tồn tại", "error")
            return redirect(url_for("login_bp.login"))  

        if not check_password_hash(user.password, password):
            flash("Mật khẩu không đúng", "error")
            return redirect(url_for("login_bp.login")) 

        if not user.approved:
            flash("Tài khoản chưa được admin duyệt", "error")
            return redirect(url_for("login_bp.login")) 
        session["user_id"] = user.id
        session["username"] = user.username
        session["is_admin"] = user.is_admin
        flash("Đăng nhập thành công!", "success")
        return redirect(url_for("admin.admin_dashboard") if user.is_admin else url_for("home"))

    return render_template("login.html")
