from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
)
from werkzeug.security import generate_password_hash
from flask_login import current_user, login_required
from .auth import get_user_by_username
from .db import get_db_connection, db_cursor
from .helpers import roles_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/list_users")
@roles_required("admin")
@login_required
def list_users():
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
    return render_template(
        "admin/list_users.html", users=users, title="Benutzerverwaltung"
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
@login_required
def edit_user(user_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            flash("Benutzer nicht gefunden.", "danger")
            return redirect(url_for("admin.list_users"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            role = request.form.get("role", "").strip()
            new_password = request.form.get("password", "").strip()
            if new_password:
                password_hash = generate_password_hash(new_password)
                cursor.execute(
                    "UPDATE users SET username = %s, role = %s, password_hash = %s WHERE id = %s",
                    (username, role, password_hash, user_id),
                )
            else:
                cursor.execute(
                    "UPDATE users SET username = %s, role = %s WHERE id = %s",
                    (username, role, user_id),
                )

            flash("Benutzer erfolgreich aktualisiert.", "success")
            return redirect(url_for("admin.list_users"))
        else:
            return render_template(
                "admin/edit_user.html", user=user, title="Benutzer bearbeiten"
            )


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@roles_required("admin")
@login_required
def delete_user(user_id):
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    flash("Benutzer erfolgreich gelöscht.", "success")
    return redirect(url_for("admin.list_users"))


@admin_bp.route("/admin/settings", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_settings():
    with db_cursor() as cursor:
        if request.method == "POST":
            # Gehe alle Settings durch und update sie
            for key in request.form:
                value = request.form.get(key)
                cursor.execute(
                    "UPDATE einstellungen SET value = %s WHERE setting_key = %s",
                    (value, key),
                )

            current_app.refresh_settings()

            flash("Einstellungen wurden gespeichert und aktualisiert.", "success")
            return redirect(url_for("admin.edit_settings"))

        # GET: zeige aktuelle Settings
        cursor.execute("SELECT setting_key, value, description FROM einstellungen")
        settings = cursor.fetchall()
        settings = {item["setting_key"]: item for item in settings}
        return render_template("admin/edit_settings.html", settings=settings)


@admin_bp.route("/users/register", methods=["GET", "POST"])
@roles_required("admin")
@login_required
def register_user():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip()
        if not username or not password or not role:
            flash("Bitte alle Felder ausfüllen.", "danger")
            return redirect(url_for("auth.create_user"))
        if get_user_by_username(username):
            flash("Benutzername existiert bereits.", "danger")
            return redirect(url_for("auth.create_user"))
        with db_cursor() as cursor:
            password_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                (username, password_hash, role),
            )
        flash("Benutzer erfolgreich angelegt.", "success")
        return redirect(url_for("admin.list_users"))
    return render_template("admin/register_user.html", title="Benutzer anlegen")
