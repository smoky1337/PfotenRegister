import io
import os
from datetime import date

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


@admin_bp.route("/")
@login_required
@roles_required("admin")
def dashboard():
    from datetime import date, timedelta
    with db_cursor() as cursor:
        # Gäste insgesamt
        cursor.execute("SELECT COUNT(*) AS total_guests FROM gaeste")
        total_guests = cursor.fetchone()["total_guests"]

        # Aktive Gäste
        cursor.execute("SELECT COUNT(*) AS active_guests FROM gaeste WHERE status = 'Aktiv'")
        active_guests = cursor.fetchone()["active_guests"]

        # Gäste mit Futterausgabe in den letzten 30 Tagen
        last_30_days = date.today() - timedelta(days=30)
        cursor.execute("SELECT COUNT(DISTINCT gast_id) AS recent_guests FROM futterhistorie WHERE futtertermin >= %s", (last_30_days,))
        recent_guests = cursor.fetchone()["recent_guests"]

        # Tiere insgesamt
        cursor.execute("SELECT COUNT(*) AS total_animals FROM tiere")
        total_animals = cursor.fetchone()["total_animals"]

        # Tiere nach Art
        cursor.execute("SELECT art, COUNT(*) AS count FROM tiere GROUP BY art")
        animals_by_type = cursor.fetchall()

        # Gäste mit den meisten Besuchen (Einträge in der Futterhistorie)
        cursor.execute("""
            SELECT g.nummer, g.vorname, g.nachname, COUNT(f.entry_id) AS besuche
            FROM gaeste g
            LEFT JOIN futterhistorie f ON g.id = f.gast_id
            GROUP BY g.id
            ORDER BY besuche DESC
            LIMIT 10
        """)
        top_guests_by_visits = cursor.fetchall()

        # Payment trends for last 30 dates
        cursor.execute("""
            SELECT f.futtertermin,
                   COALESCE(SUM(z.futter_betrag), 0) AS futter_summe,
                   COALESCE(SUM(z.zubehoer_betrag), 0) AS zubehoer_summe
            FROM futterhistorie f
            LEFT JOIN zahlungshistorie z ON f.gast_id = z.gast_id AND z.zahlungstag = f.futtertermin
            GROUP BY f.futtertermin
            ORDER BY f.futtertermin ASC
            LIMIT 30
        """)
        payment_trends = cursor.fetchall()

    return render_template(
        "admin/dashboard.html",
        total_guests=total_guests,
        active_guests=active_guests,
        recent_guests=recent_guests,
        total_animals=total_animals,
        animals_by_type=animals_by_type,
        top_guests_by_visits=top_guests_by_visits,
        payment_trends=payment_trends,
        title="Dashboard"
    )

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
def confirm_import():
    from .helpers import generate_unique_code
    from .db import db_cursor
    import pandas as pd
    import os

    filepath = request.args.get("filepath")
    safe_path = os.path.join("tmp", os.path.basename(filepath))

    if not os.path.exists(safe_path):
        flash("Datei nicht gefunden.", "danger")
        return redirect(url_for("admin.import_data"))

    dtype_guests = {
        "nummer": str,
        "vorname": str,
        "nachname": str,
        "adresse": str,
        "ort": str,
        "plz": str,
        "festnetz": str,
        "mobil": str,
        "email": str,
        "geschlecht": str,
        "status": str,
        "beduerftigkeit": str,
        "dokumente": str,
        "notizen": str,
        "vertreter_name": str,
        "vertreter_telefon": str,
        "vertreter_email": str,
        "vertreter_adresse": str
    }
    dtype_animals = {
        "gast_nummer": str,
        "art": str,
        "rasse": str,
        "name": str,
        "geschlecht": str,
        "farbe": str,
        "identifikation": str,
        "kastriert": str,
        "futter": str,
        "vollversorgung": str,
        "notizen": str
    }
    df_guests = pd.read_excel(safe_path, sheet_name="gaeste", dtype=dtype_guests)
    df_animals = pd.read_excel(safe_path, sheet_name="tiere", dtype=dtype_animals)

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

    with db_cursor() as cursor:
        today = date.today()
        for guest in df_guests.to_dict(orient="records"):
            print(guest)
            guest_id = generate_unique_code()
            guest_map[guest.get("nummer")] = guest_id
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
                guest.get("beduerftigkeit"), guest.get("beduerftig"), guest.get("dokumente"), guest.get("notizen"),
                guest.get("erstellt_am") or today, guest.get("aktualisiert_am") or today
            ))

        for animal in df_animals.to_dict(orient="records"):
            gast_id = guest_map.get(animal.get("gast_nummer"))
            if not gast_id:
                continue  # Keine gültige Zuordnung gefunden

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
                animal.get("futtermengeneintrag"), animal.get("notizen"),
                animal.get("erstellt_am") or today, animal.get("aktualisiert_am") or today
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
        dtype_guests = {
            "nummer": str,
            "vorname": str,
            "nachname": str,
            "adresse": str,
            "ort": str,
            "plz": str,
            "festnetz": str,
            "mobil": str,
            "email": str,
            "geschlecht": str,
            "status": str,
            "dokumente": str,
            "notizen": str,
            "vertreter_name": str,
            "vertreter_telefon": str,
            "vertreter_email": str,
            "vertreter_adresse": str
        }
        dtype_animals = {
            "gast_nummer": str,
            "art": str,
            "rasse": str,
            "name": str,
            "geschlecht": str,
            "farbe": str,
            "identifikation": str,
            "kastriert": str,
            "futter": str,
            "vollversorgung": str,
            "notizen": str
        }
        df_guests = pd.read_excel(safe_path, sheet_name="gaeste", dtype=dtype_guests)
        df_animals = pd.read_excel(safe_path, sheet_name="tiere", dtype=dtype_animals)
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

    date_fields_guests = ["geburtsdatum", "eintritt", "austritt", "beduerftig_bis", "erstellt_am", "aktualisiert_am"]
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

@admin_bp.route("/export", methods=["GET"])
@roles_required("admin")
@login_required
def export_data():
    from flask import send_file
    from openpyxl import load_workbook
    from openpyxl.utils.dataframe import dataframe_to_rows
    from io import BytesIO
    from datetime import date
    import pandas as pd

    template_path = os.path.join(current_app.root_path, "static", "output_template.xlsx")
    wb = load_workbook(template_path)

    ws_guests = wb["gaeste"]
    ws_animals = wb["tiere"]

    # Clear existing rows except for headers
    ws_guests.delete_rows(2, ws_guests.max_row)
    ws_animals.delete_rows(2, ws_animals.max_row)

    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM gaeste")
        guests = cursor.fetchall()
        cursor.execute("SELECT * FROM tiere")
        animals = cursor.fetchall()

    df_guests = pd.DataFrame(guests)[[
        "nummer", "vorname", "nachname", "adresse", "plz", "ort", "festnetz", "mobil", "email",
        "geburtsdatum", "geschlecht", "eintritt", "austritt",
        "vertreter_name", "vertreter_telefon", "vertreter_email", "vertreter_adresse",
        "status", "beduerftigkeit", "beduerftig_bis", "dokumente", "notizen"
    ]]

    df_animals = pd.DataFrame(animals)

    # Merge animals with guest nummer
    guest_id_to_nummer = pd.DataFrame(guests)[["id", "nummer"]].rename(columns={"id": "gast_id"})
    df_animals = df_animals.merge(guest_id_to_nummer, on="gast_id", how="left")

    # test if theres any animals without guests
    if df_animals["nummer"].isna().any():
        print("[WARNUNG] Einige Tiere konnten keiner gültigen Gastnummer zugeordnet werden.")

    df_animals.drop(columns=["gast_id"], inplace=True)
    df_animals = df_animals[[
        "nummer", "art", "rasse", "name", "geschlecht", "farbe", "kastriert", "identifikation",
        "geburtsdatum", "gewicht_oder_groesse", "krankheiten", "unvertraeglichkeiten",
        "futter", "vollversorgung", "zuletzt_gesehen", "tierarzt", "futtermengeneintrag", "notizen"
    ]]
    df_animals.rename(columns={"nummer": "gast_nummer"}, inplace=True)

    for row in dataframe_to_rows(df_guests, index=False, header=False):
        ws_guests.append(row)

    for row in dataframe_to_rows(df_animals, index=False, header=False):
        ws_animals.append(row)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"pfotenregister_export_{date.today().isoformat()}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)


@admin_bp.route("/export_transactions", methods=["GET"])
@roles_required("admin")
@login_required
def export_transactions():
    from flask import send_file
    from io import BytesIO
    from datetime import datetime
    import pandas as pd

    from_date = request.args.get("from")
    to_date = request.args.get("to")

    if not from_date or not to_date:
        flash("Bitte gib ein gültiges Start- und Enddatum an.", "danger")
        return redirect(url_for("admin.dashboard"))

    try:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d").date()
        to_dt = datetime.strptime(to_date, "%Y-%m-%d").date()
    except ValueError:
        flash("Ungültiges Datumsformat.", "danger")
        return redirect(url_for("admin.dashboard"))

    with db_cursor() as cursor:
        cursor.execute("""
            SELECT z.zahlungstag, g.nummer AS gast_nummer, g.vorname, g.nachname,
                   z.futter_betrag, z.zubehoer_betrag, z.kommentar
            FROM zahlungshistorie z
            JOIN gaeste g ON g.id = z.gast_id
            WHERE z.zahlungstag BETWEEN %s AND %s
            ORDER BY z.zahlungstag ASC
        """, (from_dt, to_dt))
        records = cursor.fetchall()

    df = pd.DataFrame(records)
    if not df.empty:
        total_futter = df["futter_betrag"].sum()
        total_zubehoer = df["zubehoer_betrag"].sum()
        df.loc[len(df.index)] = ["SUMME", "", "", "", total_futter, total_zubehoer, ""]
    else:
        # Leere DataFrame mit Spaltennamen
        df = pd.DataFrame(columns=[
            "zahlungstag", "gast_nummer", "vorname", "nachname",
            "futter_betrag", "zubehoer_betrag", "kommentar"
        ])

    return render_template(
        "reports/transaction_report.html",
        transactions=records,
        from_date=from_dt.strftime('%d.%m.%Y'),
        to_date=to_dt.strftime('%d.%m.%Y'),
        total_futter=df["futter_betrag"].sum(),
        total_zubehoer=df["zubehoer_betrag"].sum(),
        now = datetime.today(),
        title="Zahlungsbericht"
    )

    filename = f"zahlungsexport_{from_dt.isoformat()}_bis_{to_dt.isoformat()}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)