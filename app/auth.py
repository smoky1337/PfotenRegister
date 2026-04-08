from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .helpers import get_form_value
from .models import User as UserModel
from .models import db

auth_bp = Blueprint("auth", __name__)


class User(UserMixin):
    def __init__(self, model_obj: UserModel):
        self.id = model_obj.id
        self.username = model_obj.username
        self.password_hash = model_obj.password_hash
        self.role = model_obj.role
        self.realname = model_obj.realname


def get_user(user_id):
    user = UserModel.query.get(user_id)
    if user:
        return User(user)
    return None


def get_user_by_username(username):
    user = UserModel.query.filter_by(username=username).first()
    if user:
        return User(user)
    return None


def get_demo_user():
    users = UserModel.query.order_by(UserModel.id.asc()).all()
    if not users:
        return None

    preferred_roles = ("admin", "editor", "user")
    for preferred_role in preferred_roles:
        for user in users:
            if (user.role or "").strip().lower() == preferred_role:
                return User(user)

    return User(users[0])


@auth_bp.before_app_request
def ensure_demo_login():
    if not current_app.config.get("DEMO_AUTO_LOGIN"):
        return None
    if current_user.is_authenticated:
        return None

    demo_user = get_demo_user()
    if demo_user:
        login_user(demo_user, remember=False, force=True)
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_app.config.get("DEMO_AUTO_LOGIN"):
        return redirect(url_for("guest.index"))

    if current_user.is_authenticated:
        return redirect(url_for("guest.index"))

    username_value = ""
    if request.method == "POST":
        username = get_form_value("username")
        password = get_form_value("password")
        username_value = username or ""
        user = get_user_by_username(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Erfolgreich angemeldet.", "success")
            return redirect(url_for("guest.index"))
        else:
            flash("Ungültiger Benutzername oder Passwort.", "danger")
    return render_template("login.html", title="Anmeldung", username_value=username_value)


@auth_bp.route("/logout")
@login_required
def logout():
    if current_app.config.get("DEMO_AUTO_LOGIN"):
        flash("Demo-Version bleibt automatisch angemeldet.", "info")
        return redirect(url_for("guest.index"))

    logout_user()
    flash("Erfolgreich abgemeldet.", "success")
    return redirect(url_for("auth.login"))
