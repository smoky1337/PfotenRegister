import os

import pandas as pd
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
from werkzeug.utils import secure_filename

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


@admin_bp.route("/settings", methods=["GET", "POST"])
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


@admin_bp.route("/import", methods=["GET", "POST"])
@roles_required("admin")
@login_required
def import_data():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename.endswith(".xlsx"):
            flash("Bitte eine gültige .xlsx Datei hochladen.", "danger")
            return redirect(request.url)

        filepath = os.path.join("tmp", secure_filename(file.filename))
        os.makedirs("tmp", exist_ok=True)
        file.save(filepath)

        return redirect(url_for("admin.preview_import", filepath=filepath))

    return render_template("admin/import.html", title="Datenimport")

@admin_bp.route("/import/confirm", methods=["GET", "POST"])
@roles_required("admin")
@login_required
def confirm_import(filepath):
    # Import-Logik für POST
    if request.method == "POST":
        from .helpers import generate_unique_code
        import pandas as pd
        import os

        filepath = request.args.get("filepath")
        safe_path = os.path.join("tmp", os.path.basename(filepath))

        if not os.path.exists(safe_path):
            flash("Datei nicht gefunden.", "danger")
            return redirect(url_for("admin.import_data"))

        df_guests = pd.read_excel(safe_path, sheet_name="gaeste")
        df_animals = pd.read_excel(safe_path, sheet_name="tiere")

        def normalize_date(val):
            if pd.isna(val) or val == "":
                return None
            try:
                return pd.to_datetime(val, dayfirst=True).date()
            except Exception:
                return None

        def normalize_string(val):
            return val.strip() if isinstance(val, str) and val.strip() != "" else None

        for col in df_guests.columns:
            if col in ["geburtsdatum", "eintritt", "austritt", "beduerftig_bis", "erstellt_am", "aktualisiert_am"]:
                df_guests[col] = df_guests[col].apply(normalize_date)
            else:
                df_guests[col] = df_guests[col].apply(normalize_string)

        for col in df_animals.columns:
            if col in ["geburtsdatum", "zuletzt_gesehen", "erstellt_am", "aktualisiert_am"]:
                df_animals[col] = df_animals[col].apply(normalize_date)
            else:
                df_animals[col] = df_animals[col].apply(normalize_string)

        guest_map = {}

        from .db import db_cursor
        with db_cursor() as cursor:
            for guest in df_guests.to_dict(orient="records"):
                guest_id = generate_unique_code()
                guest_map[guest["nummer"]] = guest_id
                cursor.execute("""
                    INSERT INTO gaeste (
                        id, nummer, vorname, nachname, adresse, ort, plz,
                        festnetz, mobil, email, geburtsdatum, geschlecht,
                        eintritt, austritt, vertreter_name, vertreter_telefon,
                        vertreter_email, vertreter_adresse, status,
                        beduerftigkeit, beduerftig_bis, dokumente, notizen,
                        erstellt_am, aktualisiert_am
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s
                    )
                """, (
                    guest_id,
                    guest.get("nummer"), guest.get("vorname"), guest.get("nachname"), guest.get("adresse"), guest.get("ort"), guest.get("plz"),
                    guest.get("festnetz"), guest.get("mobil"), guest.get("email"), guest.get("geburtsdatum"), guest.get("geschlecht"),
                    guest.get("eintritt"), guest.get("austritt"), guest.get("vertreter_name"), guest.get("vertreter_telefon"),
                    guest.get("vertreter_email"), guest.get("vertreter_adresse"), guest.get("status"),
                    guest.get("beduerftigkeit_typ"), guest.get("beduerftig_seit"), guest.get("dokumente"), guest.get("notizen"),
                    guest.get("erstellt_am"), guest.get("aktualisiert_am")
                ))

            for animal in df_animals.to_dict(orient="records"):
                gast_id = guest_map.get(animal.get("gast_nummer"))
                if not gast_id:
                    continue  # Gastnummer wurde nicht gemappt

                cursor.execute("""
                    INSERT INTO tiere (
                        gast_id, art, rasse, name, geschlecht, farbe, kastriert, identifikation,
                        geburtsdatum, gewicht_oder_groesse, krankheiten, unvertraeglichkeiten,
                        futter, vollversorgung, zuletzt_gesehen, tierarzt, futtermengeneintrag,
                        notizen, erstellt_am, aktualisiert_am
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s
                    )
                """, (
                    gast_id, animal.get("art"), animal.get("rasse"), animal.get("name"), animal.get("geschlecht"), animal.get("farbe"),
                    animal.get("kastriert"), animal.get("identifikation"), animal.get("geburtsdatum"),
                    animal.get("gewicht_oder_groesse"), animal.get("krankheiten"), animal.get("unvertraeglichkeiten"),
                    animal.get("futter"), animal.get("vollversorgung"), animal.get("zuletzt_gesehen"), animal.get("tierarzt"),
                    animal.get("futtermengeneintrag"), animal.get("notizen"), animal.get("erstellt_am"), animal.get("aktualisiert_am")
                ))

        flash("Import erfolgreich durchgeführt.", "success")
        return redirect(url_for("admin.import_data"))


@admin_bp.route("/import/preview")
@roles_required("admin")
@login_required
def preview_import():
    filepath = request.args.get("filepath")

    if not filepath:
        flash("Kein Dateipfad angegeben.", "danger")
        return redirect(url_for("admin.import_data"))

    # Sicherheitshalber: Nur Zugriff auf tmp-Ordner zulassen
    safe_path = os.path.join("tmp", os.path.basename(filepath))
    if not os.path.exists(safe_path):
        flash("Die Datei wurde nicht gefunden.", "danger")
        return redirect(url_for("admin.import_data"))

    try:
        df_guests = pd.read_excel(safe_path, sheet_name="gaeste")
        df_animals = pd.read_excel(safe_path, sheet_name="tiere")
        print(df_guests)
        print(df_animals)
    except Exception as e:
        flash(f"Fehler beim Einlesen der Datei: {e}", "danger")
        return redirect(url_for("admin.import_data"))

    # --- Datenvalidierung und Normalisierung ---
    def normalize_date(val):
        if pd.isna(val) or val == "":
            return None
        try:
            return pd.to_datetime(val, dayfirst=True).date()
        except Exception:
            return None

    def normalize_string(val):
        return val.strip() if isinstance(val, str) and val.strip() != "" else None

    date_fields_guests = ["geburtsdatum", "eintritt", "austritt", "beduerftig_seit", "beduerftig_bis", "erstellt_am", "aktualisiert_am"]
    string_fields_guests = [
        "nummer",
        "vorname",
        "nachname",
        "adresse",
        "ort",
        "plz",
        "festnetz",
        "mobil",
        "email",
        "geschlecht",
        "status",
        "dokumente",
        "notizen",
        "vertreter_name",
        "vertreter_telefon",
        "vertreter_email",
        "vertreter_adresse",
    ]

    # Alle stringrelevanten Felder explizit als String casten
    for field in string_fields_guests:
        if field in df_guests.columns:
            df_guests[field] = df_guests[field].astype(str)

    for field in date_fields_guests:
        if field in df_guests.columns:
            df_guests[field] = df_guests[field].apply(normalize_date)

    for field in string_fields_guests:
        if field in df_guests.columns:
            df_guests[field] = df_guests[field].apply(normalize_string)

    date_fields_animals = ["geburtsdatum", "zuletzt_gesehen", "erstellt_am", "aktualisiert_am"]
    string_fields_animals = [
        "gast_nummer",
        "art",
        "rasse",
        "name",
        "geschlecht",
        "farbe",
        "identifikation",
        "kastriert",
        "futter",
        "vollversorgung",
        "notizen",
    ]

    for field in string_fields_animals:
        if field in df_animals.columns:
            df_animals[field] = df_animals[field].astype(str)

    for field in date_fields_animals:
        if field in df_animals.columns:
            df_animals[field] = df_animals[field].apply(normalize_date)

    for field in string_fields_animals:
        if field in df_animals.columns:
            df_animals[field] = df_animals[field].apply(normalize_string)


    # Validation: Check for missing or empty gast_nummer in animals
    missing_guest_number = []
    for idx, row in df_animals.iterrows():
        if pd.isna(row.get("gast_nummer")) or str(row.get("gast_nummer")).strip() == "":
            missing_guest_number.append(idx + 2)  # Excel-style row number

    if missing_guest_number:
        flash(f"Einige Tiere haben keine gültige Gastnummer (z. B. Zeile(n): {', '.join(map(str, missing_guest_number))}).", "danger")



    # Check for duplicate guests by vorname, nachname, adresse
    with db_cursor() as cursor:
        # Check for duplicate guest numbers in the imported file
        duplicate_numbers = df_guests["nummer"].value_counts()
        duplicates = duplicate_numbers[duplicate_numbers > 1]
        if not duplicates.empty:
            flash(f"Die folgenden Gastnummern sind mehrfach in der Datei vorhanden: {', '.join(duplicates.index)}",
                  "danger")

        # Check for guest numbers that already exist in the database
        existing_numbers = []
        for nummer in df_guests["nummer"].dropna().unique():
            nummer = str(nummer)
            cursor.execute("SELECT id FROM gaeste WHERE nummer = %s", (nummer,))
            if cursor.fetchone():
                existing_numbers.append(nummer)

        if existing_numbers:
            flash(f"Die folgenden Gastnummern existieren bereits in der Datenbank: {', '.join(existing_numbers)}",
                  "danger")

        existing_guests = []
        for guest in df_guests.to_dict(orient="records"):
            if not guest.get("vorname") or not guest.get("nachname") or not guest.get("adresse"):
                continue  # skip if necessary fields are missing
            cursor.execute(
                "SELECT id FROM gaeste WHERE vorname = %s AND nachname = %s AND adresse = %s",
                (guest["vorname"], guest["nachname"], guest["adresse"])
            )
            if cursor.fetchone():
                existing_guests.append(f'{guest["vorname"]} {guest["nachname"]} ({guest["adresse"]})')

        if existing_guests:
            flash(f"Folgende Gäste existieren bereits: {', '.join(existing_guests)}", "warning")



    return render_template(
        "admin/import_preview.html",
        guests=df_guests.to_dict(orient="records"),
        animals=df_animals.to_dict(orient="records"),
        filepath=safe_path,
        title="Importvorschau"
    )