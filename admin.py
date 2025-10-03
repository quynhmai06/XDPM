from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from models import db, User

admin_bp = Blueprint("admin", __name__)

def require_admin():
    if not session.get("is_admin"):
        return False
    return True

@admin_bp.route("/admin", methods=["GET"], endpoint="admin_dashboard")
def admin_dashboard():
    if not require_admin():
        return render_template("admin.html", users=[], products=[], transactions=[])

    users = User.query.order_by(User.id.desc()).all()        
    products = []                                          
    transactions = []                                       

    return render_template("admin.html", users=users, products=products, transactions=transactions)

@admin_bp.route("/admin/login", methods=["GET", "POST"], endpoint="admin_login")
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username, is_admin=True).first()
        if not user:
            flash("❌ Không tìm thấy tài khoản admin", "error")
            return redirect("/admin#login")

        if not check_password_hash(user.password, password):
            flash("❌ Sai mật khẩu", "error")
            return redirect("/admin#login")

        session["admin_id"] = user.id
        session["is_admin"] = True
        session["username"] = user.username
        flash("✅ Đăng nhập thành công!", "success")
        return redirect(url_for("admin.admin_dashboard"))

    return render_template("admin.html", users=[], products=[], transactions=[])

@admin_bp.route("/admin/logout", methods=["GET"], endpoint="logout")
def logout():
    session.clear()
    flash("✅ Đã đăng xuất!", "success")
    return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/admin/approve_user/<int:user_id>", methods=["POST", "GET"])
def approve_user(user_id):
    if not require_admin():
        flash("Bạn cần đăng nhập admin", "error")
        return redirect("/admin#login")
    user = User.query.get_or_404(user_id)
    user.approved = True
    db.session.commit()
    flash(f"✅ Đã duyệt tài khoản: {user.username}", "success")
    return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/admin/users/<int:user_id>/status", methods=["POST"], endpoint="update_user_status")
def update_user_status(user_id):
    if not session.get("is_admin"):
        flash("Bạn cần đăng nhập admin", "error")
        return redirect(url_for("admin.admin_dashboard"))

    u = User.query.get_or_404(user_id)
    new_status = request.form.get("approved")

    if new_status == "1":
        u.approved = True
    else:
        u.approved = False

    db.session.commit()
    flash(f"✅ Cập nhật trạng thái cho {u.username}", "success")
    return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/admin/delete_user/<int:user_id>", methods=["GET"])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("Tài khoản đã bị xóa!", "success")
    return redirect(url_for("admin.admin_dashboard"))
