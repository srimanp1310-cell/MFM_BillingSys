from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import bp
from app.auth.forms import LoginForm, UserForm
from app.extensions import db
from app.models import User
from app.utils import admin_required


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip().lower()).first()
        if user is None or not user.check_password(form.password.data) or not user.is_active:
            flash("Invalid username or password.", "danger")
        else:
            login_user(user, remember=form.remember.data)
            next_page = request.args.get("next")
            if not next_page or not next_page.startswith("/"):
                next_page = url_for("main.index")
            return redirect(next_page)
    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("auth.login"))


# --- user management (admin) ---


@bp.route("/users")
@admin_required
def users():
    all_users = User.query.order_by(User.username).all()
    return render_template("auth/users.html", users=all_users, form=UserForm())


@bp.route("/users/new", methods=["POST"])
@admin_required
def create_user():
    form = UserForm()
    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
        elif not form.password.data:
            flash("Password is required for a new user.", "danger")
        else:
            user = User(username=username, role=form.role.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash(f"User '{username}' created.", "success")
    else:
        flash("Could not create user — check the fields.", "danger")
    return redirect(url_for("auth.users"))


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
    else:
        user.is_active_flag = not user.is_active_flag
        db.session.commit()
        state = "activated" if user.is_active_flag else "deactivated"
        flash(f"User '{user.username}' {state}.", "success")
    return redirect(url_for("auth.users"))


@bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def reset_password(user_id):
    user = db.get_or_404(User, user_id)
    new_password = request.form.get("password", "").strip()
    if len(new_password) < 6:
        flash("Password must be at least 6 characters.", "danger")
    else:
        user.set_password(new_password)
        db.session.commit()
        flash(f"Password reset for '{user.username}'.", "success")
    return redirect(url_for("auth.users"))
