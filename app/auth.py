from flask import Blueprint, render_template, request, redirect, url_for, flash
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


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = get_form_value("username")
        password = get_form_value("password")
        user = get_user_by_username(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Erfolgreich angemeldet.", "success")
            return redirect(url_for("guest.index"))
        else:
            flash("Ungültiger Benutzername oder Passwort.", "danger")
            return redirect(url_for("auth.login"))
    return render_template("login.html", title="Anmeldung")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Erfolgreich abgemeldet.", "success")
    return redirect(url_for("auth.login"))
