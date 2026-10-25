from typing import Dict, Iterable, Tuple, Type

from sqlalchemy import Date, DateTime

from .models import FieldRegistry, db


FIELD_MODEL_LABELS = {
    "Guest": "Gäste",
    "Animal": "Tiere",
    "Representative": "Vertretungen",
}

FIELD_UI_LABELS: Dict[str, Dict[str, str]] = {
    "Guest": {
        "id": "Interne ID",
        "number": "Gastnummer",
        "firstname": "Vorname",
        "lastname": "Nachname",
        "address": "Adresse",
        "city": "Ort",
        "zip": "Postleitzahl",
        "phone": "Festnetz",
        "mobile": "Mobilnummer",
        "email": "E-Mail-Adresse",
        "birthdate": "Geburtsdatum",
        "gender": "Geschlecht",
        "member_since": "Mitglied seit",
        "member_until": "Mitglied bis",
        "status": "Aktiv",
        "lifecycle_status": "Bearbeitungsstatus",
        "indigence": "Bedürftigkeit",
        "indigent_until": "Bedürftig bis",
        "documents": "Dokumente",
        "notes": "Notizen",
        "created_on": "Erstellt am",
        "updated_on": "Aktualisiert am",
        "guest_card_printed_on": "Gästekarte gedruckt am",
        "guest_card_emailed_on": "Gästekarte versendet am",
        "dispense_location_id": "Ausgabestandort",
    },
    "Animal": {
        "id": "Interne ID",
        "guest_id": "Gast",
        "species": "Tierart",
        "breed": "Rasse",
        "name": "Name",
        "sex": "Geschlecht",
        "color": "Farbe",
        "castrated": "Kastriert",
        "identification": "Kennzeichnung",
        "birthdate": "Geburtsdatum",
        "weight_or_size": "Gewicht / Größe",
        "illnesses": "Erkrankungen",
        "allergies": "Allergien",
        "food_type": "Futterart",
        "complete_care": "Vollversorgung",
        "last_seen": "Zuletzt gesehen",
        "veterinarian": "Tierarzt / Tierärztin",
        "food_amount_note": "Hinweis zur Futtermenge",
        "note": "Notiz",
        "created_on": "Erstellt am",
        "updated_on": "Aktualisiert am",
        "status": "Aktiv",
        "tax_until": "Hundesteuer gültig bis",
        "pet_registry": "Haustierregister",
        "died_on": "Verstorben am",
        "profile_attachment_id": "Profilbild",
    },
    "Representative": {
        "id": "Interne ID",
        "name": "Name",
        "phone": "Telefon",
        "email": "E-Mail-Adresse",
        "address": "Adresse",
        "guest_id": "Gast",
    },
}


def legacy_field_label(field_name: str) -> str:
    """Return the former automatically generated English label."""
    return field_name.replace("_", " ").capitalize()


def get_default_field_label(model_name: str, field_name: str) -> str:
    """Return the German default label or a readable technical fallback."""
    return FIELD_UI_LABELS.get(model_name, {}).get(
        field_name,
        legacy_field_label(field_name),
    )


def ensure_field_registry(models: Iterable[Type]) -> Tuple[int, int]:
    """Create missing registry rows and translate untouched legacy labels."""
    existing_fields = {
        (field.model_name, field.field_name): field
        for field in FieldRegistry.query.filter(
            FieldRegistry.model_name.in_(tuple(FIELD_MODEL_LABELS))
        ).all()
    }
    created_count = 0
    translated_count = 0

    for model in models:
        model_name = model.__name__
        if model_name not in FIELD_MODEL_LABELS:
            continue
        for column in model.__table__.columns:
            field_name = column.name
            default_label = get_default_field_label(model_name, field_name)
            field = existing_fields.get((model_name, field_name))
            if field:
                if (
                    field.ui_label == legacy_field_label(field_name)
                    and field.ui_label != default_label
                ):
                    field.ui_label = default_label
                    translated_count += 1
                continue

            is_optional = (
                column.nullable
                or column.default is not None
                or column.server_default is not None
            )
            db.session.add(
                FieldRegistry(
                    model_name=model_name,
                    field_name=field_name,
                    globally_visible=True,
                    optional=is_optional,
                    visibility_level="User",
                    editability_level="Editor",
                    ui_label=default_label,
                    show_inline=True,
                    display_order=0,
                    remindable=isinstance(column.type, (Date, DateTime)),
                )
            )
            created_count += 1

    if created_count or translated_count:
        db.session.commit()
    return created_count, translated_count
