from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .db import get_db_connection, db_cursor
from .helpers import get_form_value

auth_bp = Blueprint("auth", __name__)


class User(UserMixin):
    def __init__(self, id, username, password_hash, role, realname):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.realname = realname


def get_user(user_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
    if row:
        return User(row["id"], row["username"], row["password_hash"], row["role"], row["realname"])
    return None


def get_user_by_username(username):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = cursor.fetchone()
    if row:
        return User(row["id"], row["username"], row["password_hash"], row["role"], row["realname"])
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
