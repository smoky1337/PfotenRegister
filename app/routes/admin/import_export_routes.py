import os
from collections import Counter
from datetime import date, datetime

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

from ...helpers import generate_unique_code, roles_required
from ...models import Animal, Guest, Representative, db

admin_io_bp = Blueprint('admin_io', __name__, url_prefix='/admin')

# Expected column names/types from the Excel template
GUEST_DTYPES = {
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
    "vertreter_adresse": str,
}
ANIMAL_DTYPES = {
    "gast_nummer": str,
    "art": str,
    "rasse": str,
    "name": str,
    "geschlecht": str,
    "active": str,
    "farbe": str,
    "kastriert": str,
    "identifikation": str,
    "geburtsdatum": str,
    "gewicht_oder_groesse": str,
    "krankheiten": str,
    "unvertraeglichkeiten": str,
    "futter": str,
    "vollversorgung": str,
    "zuletzt_gesehen": str,
    "steuerbescheid_bis": str,
    "tierarzt": str,
    "futtermengeneintrag": str,
    "notizen": str,
}

DATE_FIELDS_GUESTS = [
    "geburtsdatum",
    "eintritt",
    "austritt",
    "beduerftig_bis",
    "erstellt_am",
    "aktualisiert_am",
]
STRING_FIELDS_GUESTS = list(GUEST_DTYPES.keys())

DATE_FIELDS_ANIMALS = [
    "geburtsdatum",
    "zuletzt_gesehen",
    "erstellt_am",
    "aktualisiert_am",
    "steuerbescheid_bis",
]
STRING_FIELDS_ANIMALS = list(ANIMAL_DTYPES.keys())

TRUE_VALUES = {"1", "ja", "true", "wahr", "y", "yes", "aktiv", "active", "x"}
FALSE_VALUES = {"0", "nein", "false", "falsch", "n", "no", "inaktiv", "inactive"}


def _safe_tmp_path(filepath: str):
    if not filepath:
        return None
    return os.path.join("tmp", os.path.basename(filepath))


def _normalize_date(val):
    if pd.isna(val) or val == "":
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        converted = pd.to_datetime(val, dayfirst=True, errors="coerce")
        return converted.date() if not pd.isna(converted) else None
    except Exception:
        return None


def _normalize_string(val):
    return val.strip() if isinstance(val, str) and val.strip() != "" else None


def _normalize_dataframe(df, date_fields, string_fields):
    for field in date_fields:
        if field in df.columns:
            df[field] = df[field].apply(_normalize_date)
    for field in string_fields:
        if field in df.columns:
            df[field] = df[field].apply(_normalize_string)
    return df


def _read_import_file(safe_path):
    df_guests = pd.read_excel(safe_path, sheet_name="gaeste", dtype=GUEST_DTYPES)
    df_animals = pd.read_excel(safe_path, sheet_name="tiere", dtype=ANIMAL_DTYPES)
    df_guests = _normalize_dataframe(df_guests, DATE_FIELDS_GUESTS, STRING_FIELDS_GUESTS)
    df_animals = _normalize_dataframe(df_animals, DATE_FIELDS_ANIMALS, STRING_FIELDS_ANIMALS)
    return df_guests.to_dict(orient="records"), df_animals.to_dict(orient="records")


def _parse_bool(val, default=None):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    if isinstance(val, bool):
        return val
    text = str(val).strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return default


def _map_gender(value):
    if not value:
        return "Unbekannt"
    text = str(value).strip().lower()
    mapping = {
        "frau": "Frau",
        "weiblich": "Frau",
        "w": "Frau",
        "mann": "Mann",
        "maennlich": "Mann",
        "männlich": "Mann",
        "m": "Mann",
        "divers": "Divers",
        "d": "Divers",
        "unbekannt": "Unbekannt",
        "u": "Unbekannt",
    }
    return mapping.get(text, "Unbekannt")


def _map_animal_sex(value):
    if not value:
        return "Unbekannt"
    text = str(value).strip().lower()
    mapping = {
        "m": "M",
        "male": "M",
        "mann": "M",
        "maennlich": "M",
        "männlich": "M",
        "w": "F",
        "f": "F",
        "weiblich": "F",
        "female": "F",
        "unknown": "Unbekannt",
        "unbekannt": "Unbekannt",
    }
    return mapping.get(text, "Unbekannt")


def _map_choice(value, allowed, default=None):
    if not value:
        return default
    cleaned = str(value).strip()
    if cleaned in allowed:
        return cleaned
    lower_map = {str(v).lower(): v for v in allowed}
    mapped = lower_map.get(cleaned.lower())
    return mapped if mapped in allowed else default


def _map_yes_no_unknown(value, default="Unbekannt"):
    return _map_choice(value, {"Ja", "Nein", "Unbekannt"}, default=default)


def _map_species(value):
    return _map_choice(value, {"Hund", "Katze", "Vogel", "Nager", "Sonstige"})


def _map_food_type(value):
    return _map_choice(value, {"Misch", "Trocken", "Nass", "Barf"})

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

        return redirect(url_for("admin_io.preview_import", filepath=filepath))

    return render_template("admin/import.html", title="Datenimport")

@admin_io_bp.route("/import/confirm", methods=["GET", "POST"])
@roles_required("admin")
@login_required
def confirm_import():
    filepath = request.args.get("filepath")
    safe_path = _safe_tmp_path(filepath)

    if not safe_path or not os.path.exists(safe_path):
        flash("Datei nicht gefunden.", "danger")
        return redirect(url_for("admin_io.import_data"))

    try:
        guests, animals = _read_import_file(safe_path)
    except Exception as exc:
        flash(f"Fehler beim Einlesen der Datei: {exc}", "danger")
        return redirect(url_for("admin_io.import_data"))

    today = date.today()
    guest_objects = []
    representative_objects = []
    animal_objects = []
    guest_map = {}
    skipped_guests = []
    skipped_animals = []

    for guest in guests:
        number = guest.get("nummer")
        firstname = guest.get("vorname")
        lastname = guest.get("nachname")
        if not number or not firstname or not lastname:
            skipped_guests.append(number or "(ohne Nummer)")
            continue

        guest_id = generate_unique_code()
        guest_map[number] = guest_id
        guest_obj = Guest(
            id=guest_id,
            number=str(number),
            firstname=firstname,
            lastname=lastname,
            address=guest.get("adresse"),
            city=guest.get("ort"),
            zip=guest.get("plz"),
            phone=guest.get("festnetz"),
            mobile=guest.get("mobil"),
            email=guest.get("email"),
            birthdate=guest.get("geburtsdatum"),
            gender=_map_gender(guest.get("geschlecht")),
            member_since=guest.get("eintritt") or today,
            member_until=guest.get("austritt"),
            status=_parse_bool(guest.get("status"), default=True),
            indigence=guest.get("beduerftigkeit"),
            indigent_until=guest.get("beduerftig_bis"),
            documents=guest.get("dokumente"),
            notes=guest.get("notizen"),
            created_on=guest.get("erstellt_am") or today,
            updated_on=guest.get("aktualisiert_am") or today,
        )
        guest_objects.append(guest_obj)

        if any(
            guest.get(key)
            for key in ("vertreter_name", "vertreter_telefon", "vertreter_email", "vertreter_adresse")
        ):
            representative_objects.append(
                Representative(
                    guest_id=guest_id,
                    name=guest.get("vertreter_name"),
                    phone=guest.get("vertreter_telefon"),
                    email=guest.get("vertreter_email"),
                    address=guest.get("vertreter_adresse"),
                )
            )

    for animal in animals:
        guest_id = guest_map.get(animal.get("gast_nummer"))
        if not guest_id:
            skipped_animals.append(animal.get("name") or "(Tier ohne Name)")
            continue

        animal_obj = Animal(
            guest_id=guest_id,
            species=_map_species(animal.get("art")),
            breed=animal.get("rasse"),
            name=animal.get("name"),
            sex=_map_animal_sex(animal.get("geschlecht")),
            color=animal.get("farbe"),
            castrated=_map_yes_no_unknown(animal.get("kastriert")),
            identification=animal.get("identifikation"),
            birthdate=animal.get("geburtsdatum"),
            weight_or_size=animal.get("gewicht_oder_groesse"),
            illnesses=animal.get("krankheiten"),
            allergies=animal.get("unvertraeglichkeiten"),
            food_type=_map_food_type(animal.get("futter")),
            complete_care=_map_yes_no_unknown(animal.get("vollversorgung")),
            last_seen=animal.get("zuletzt_gesehen"),
            veterinarian=animal.get("tierarzt"),
            food_amount_note=animal.get("futtermengeneintrag"),
            note=animal.get("notizen"),
            status=_parse_bool(animal.get("active"), default=True),
            tax_until=animal.get("steuerbescheid_bis"),
            created_on=animal.get("erstellt_am") or today,
            updated_on=animal.get("aktualisiert_am") or today,
        )
        animal_objects.append(animal_obj)

    try:
        db.session.add_all(guest_objects + representative_objects + animal_objects)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        flash(f"Fehler beim Import: {exc}", "danger")
        return redirect(url_for("admin_io.preview_import", filepath=safe_path))

    if skipped_guests:
        flash(
            f"{len(skipped_guests)} Gäste wurden übersprungen, da Pflichtfelder fehlen: {', '.join(skipped_guests)}",
            "warning",
        )
    if skipped_animals:
        flash(
            f"{len(skipped_animals)} Tiere wurden übersprungen, weil keine passende Gastnummer gefunden wurde: {', '.join(skipped_animals)}",
            "warning",
        )

    flash("Import erfolgreich durchgeführt.", "success")
    return redirect(url_for("admin_io.import_data"))


@admin_io_bp.route("/import/preview")
@roles_required("admin")
@login_required
def preview_import():
    filepath = request.args.get("filepath")
    safe_path = _safe_tmp_path(filepath)

    if not filepath or not safe_path:
        flash("Kein Dateipfad angegeben.", "danger")
        return redirect(url_for("admin_io.import_data"))

    if not os.path.exists(safe_path):
        flash("Die Datei wurde nicht gefunden.", "danger")
        return redirect(url_for("admin_io.import_data"))

    try:
        guests, animals = _read_import_file(safe_path)
    except Exception as exc:
        flash(f"Fehler beim Einlesen der Datei: {exc}", "danger")
        return redirect(url_for("admin_io.import_data"))

    # Validation: duplicates, existing entries, and missing references
    missing_guest_number = []
    missing_guest_reference = []

    guest_numbers = [g.get("nummer") for g in guests if g.get("nummer")]
    duplicates = [n for n, count in Counter(guest_numbers).items() if count > 1]
    if duplicates:
        flash(
            f"Die folgenden Gastnummern sind mehrfach in der Datei vorhanden: {', '.join(duplicates)}",
            "danger",
        )

    existing_numbers = []
    if guest_numbers:
        existing_numbers = [
            nummer
            for nummer in set(guest_numbers)
            if Guest.query.filter_by(number=nummer).first()
        ]
        if existing_numbers:
            flash(
                f"Die folgenden Gastnummern existieren bereits in der Datenbank: {', '.join(existing_numbers)}",
                "danger",
            )

    existing_guests = []
    for guest in guests:
        if not guest.get("vorname") or not guest.get("nachname") or not guest.get("adresse"):
            continue
        exists = Guest.query.filter_by(
            firstname=guest["vorname"],
            lastname=guest["nachname"],
            address=guest["adresse"],
        ).first()
        if exists:
            existing_guests.append(f'{guest["vorname"]} {guest["nachname"]} ({guest["adresse"]})')

    if existing_guests:
        flash(f"Folgende Gäste existieren bereits: {', '.join(existing_guests)}", "warning")

    for idx, row in enumerate(animals):
        guest_number = row.get("gast_nummer")
        if pd.isna(guest_number) or not str(guest_number).strip():
            missing_guest_number.append(idx + 2)
        elif guest_number not in guest_numbers:
            missing_guest_reference.append(f"{guest_number} (Zeile {idx + 2})")

    if missing_guest_number:
        flash(
            f"Einige Tiere haben keine gültige Gastnummer (z. B. Zeilen: {', '.join(map(str, missing_guest_number))}).",
            "danger",
        )
    if missing_guest_reference:
        flash(
            f"Tiere ohne passende Gastnummer in dieser Datei: {', '.join(missing_guest_reference)}. "
            f"Diese Tiere werden übersprungen.",
            "warning",
        )

    return render_template(
        "admin/import_preview.html",
        guests=guests,
        animals=animals,
        filepath=safe_path,
        title="Importvorschau",
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
