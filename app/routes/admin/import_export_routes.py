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
)
from flask_login import login_required
from werkzeug.utils import secure_filename

from ...helpers import roles_required

admin_io_bp = Blueprint('admin_io', __name__, url_prefix='/admin')

@admin_io_bp.route("/import", methods=["GET", "POST"])
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

@admin_io_bp.route("/import/confirm", methods=["GET", "POST"])
@roles_required("admin")
@login_required
def confirm_import():
    from ...helpers import generate_unique_code
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
        "notizen": str,
        "active": str
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
        if col in ["geburtsdatum", "zuletzt_gesehen", "erstellt_am", "aktualisiert_am", "steuerbescheid_bis"]:
            df_animals[col] = df_animals[col].apply(normalize_date)
        else:
            df_animals[col] = df_animals[col].apply(normalize_string)

    guest_map = {}

    with db_cursor() as cursor:
        today = date.today()
        for guest in df_guests.to_dict(orient="records"):
            print(guest)
            guest_id = generate_unique_code()
            status = guest.get("status")
            if not status:
                status = "Aktiv"
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
                guest.get("vertreter_email"), guest.get("vertreter_adresse"), status,
                guest.get("beduerftigkeit"), guest.get("beduerftig"), guest.get("dokumente"), guest.get("notizen"),
                guest.get("erstellt_am") or today, guest.get("aktualisiert_am") or today
            ))

        for animal in df_animals.to_dict(orient="records"):
            guest_id = guest_map.get(animal.get("gast_nummer"))
            if not guest_id:
                continue  # Keine gültige Zuordnung gefunden

            cursor.execute("""
                INSERT INTO tiere (
                    guest_id, art, rasse, name, geschlecht, farbe, kastriert, identifikation,
                    geburtsdatum, gewicht_oder_groesse, krankheiten, unvertraeglichkeiten,
                    futter, vollversorgung, zuletzt_gesehen, tierarzt, futtermengeneintrag,
                    notizen, active, steuerbescheid_bis, erstellt_am, aktualisiert_am
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            """, (
                guest_id, animal.get("art"), animal.get("rasse"), animal.get("name"), animal.get("geschlecht"), animal.get("farbe"),
                animal.get("kastriert"), animal.get("identifikation"), animal.get("geburtsdatum"),
                animal.get("gewicht_oder_groesse"), animal.get("krankheiten"), animal.get("unvertraeglichkeiten"),
                animal.get("futter"), animal.get("vollversorgung"), animal.get("zuletzt_gesehen"), animal.get("tierarzt"),
                animal.get("futtermengeneintrag"), animal.get("notizen"), animal.get("aktiv"), animal.get("steuerbescheid_bis"),
                animal.get("erstellt_am") or today, animal.get("aktualisiert_am") or today
            ))

    flash("Import erfolgreich durchgeführt.", "success")
    return redirect(url_for("admin.import_data"))


@admin_io_bp.route("/import/preview")
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
            "notizen": str,
            "aktiv": str,
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

    date_fields_animals = ["geburtsdatum", "zuletzt_gesehen", "erstellt_am", "aktualisiert_am", "steuerbescheid_bis"]
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


@admin_io_bp.route("/export", methods=["GET", "POST"])
@roles_required("admin")
@login_required
def export_data():
    """Render export UI (GET) or generate an Excel export (POST) using SQLAlchemy.
    - Each selected table is exported to its own sheet.
    - Selected columns are respected; unknown columns are ignored safely.
    - Uses ORM models and `load_only` for efficient column selection.
    """
    from flask import send_file
    from io import BytesIO
    from sqlalchemy.orm import load_only
    from datetime import date
    from ...models import Guest, Animal, Payment, Message, Representative, db

    if request.method == "GET":
        return render_template("admin/export.html", title="Daten exportieren")

    # POST: collect selection from the form
    include_header = request.form.get("include_header") is not None
    selections = {
        "guests": request.form.getlist("fields[guests][]"),
        "animals": request.form.getlist("fields[animals][]"),
        "payments": request.form.getlist("fields[payments][]"),
        "messages": request.form.getlist("fields[messages][]"),
        "representatives": request.form.getlist("fields[representatives][]"),
    }
    # Map from UI field keys -> ORM attribute names (identity mapping, English names)
    FIELD_MAP = {
        "guests": {
            "address": "address",
            "birthdate": "birthdate",
            "city": "city",
            "created_on": "created_on",
            "documents": "documents",
            "email": "email",
            "firstname": "firstname",
            "gender": "gender",
            "guest_card_printed_on": "guest_card_printed_on",
            "id": "id",
            "indigence": "indigence",
            "indigent_until": "indigent_until",
            "lastname": "lastname",
            "member_since": "member_since",
            "member_until": "member_until",
            "mobile": "mobile",
            "notes": "notes",
            "number": "number",
            "phone": "phone",
            "status": "status",
            "updated_on": "updated_on",
            "zip": "zip",
        },
        "animals": {
            "allergies": "allergies",
            "birthdate": "birthdate",
            "breed": "breed",
            "castrated": "castrated",
            "color": "color",
            "complete_care": "complete_care",
            "created_on": "created_on",
            "died_on": "died_on",
            "food_amount_note": "food_amount_note",
            "food_type": "food_type",
            "guest_id": "guest_id",
            "id": "id",
            "identification": "identification",
            "illnesses": "illnesses",
            "last_seen": "last_seen",
            "name": "name",
            "note": "note",
            "pet_registry": "pet_registry",
            "sex": "sex",
            "species": "species",
            "status": "status",
            "tax_until": "tax_until",
            "updated_on": "updated_on",
            "veterinarian": "veterinarian",
            "weight_or_size": "weight_or_size",
        },
        "payments": {
            "comment": "comment",
            "created_on": "created_on",
            "food_amount": "food_amount",
            "guest_id": "guest_id",
            "id": "id",
            "other_amount": "other_amount",
            "paid": "paid",
            "paid_on": "paid_on",
        },
        "messages": {
            "completed": "completed",
            "content": "content",
            "created_by": "created_by",
            "created_on": "created_on",
            "guest_id": "guest_id",
            "id": "id",
        },
        "representatives": {
            "address": "address",
            "email": "email",
            "guest_id": "guest_id",
            "id": "id",
            "name": "name",
            "phone": "phone",
        },
    }
    TABLE_MODEL = {
        "guests": (Guest, "guests"),
        "animals": (Animal, "animals"),
        "payments": (Payment, "payments"),
        "messages": (Message, "messages"),
        "representatives": (Representative, "representatives"),
    }

    # Helper: build DataFrame from ORM query
    def rows_to_df(model, cols_ui, table_key):
        if model is None or not cols_ui:
            return None
        ui_to_attr = FIELD_MAP.get(table_key, {})
        attr_names = [ui_to_attr.get(c) for c in cols_ui]
        attr_names = [a for a in attr_names if a and hasattr(model, a)]
        if not attr_names:
            return None
        load_columns = [getattr(model, a) for a in attr_names]
        q = db.session.query(model).options(load_only(*load_columns))
        results = q.all()
        rows = []
        for obj in results:
            row = []
            for ui_col in cols_ui:
                attr = ui_to_attr.get(ui_col)
                val = getattr(obj, attr, None) if attr and hasattr(obj, attr) else None
                if hasattr(val, "isoformat"):
                    try:
                        val = val.isoformat()
                    except Exception:
                        pass
                row.append(val)
            rows.append(row)
        headers = cols_ui if include_header else None
        df = pd.DataFrame(rows, columns=headers if headers else None)
        return df

    # Build the Excel in-memory
    output = BytesIO()
    any_sheet = False
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for key, (model, sheet_name) in TABLE_MODEL.items():
            cols = selections.get(key) or []
            df = rows_to_df(model, cols, key)
            if df is None:
                continue
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=include_header)
            any_sheet = True
    if not any_sheet:
        flash("Bitte wähle mindestens eine Spalte aus.", "warning")
        return render_template("admin/export.html", title="Daten exportieren")

    output.seek(0)
    filename = f"pfotenregister_export_{date.today().isoformat()}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)
