from typing import Dict, Tuple

from .models import Setting, db


DEFAULT_SETTINGS: Dict[str, Tuple[str, str]] = {
    "name": ("PfotenRegister", "Name des Vereins für die Benutzeroberfläche"),
    "primarycolour": ("#1b4750", "Primärfarbe der Benutzeroberfläche"),
    "primaryColor": ("#1b4750", "Primärfarbe der Benutzeroberfläche"),
    "logourl": ("", "URL des Logos"),
    "maxAnimals": ("2", "Maximale Anzahl an Tieren pro Gast"),
    "minTimeFood": ("21", "Mindestanzahl an Tagen zwischen Futterausgaben"),
    "maxTimeSeen": ("90", "Maximale Anzahl an Tagen bis zur Wiedervorstellung"),
    "adminEmail": ("", "Kontakt-E-Mail der Administration"),
    "payments": ("Aktiv", "Zahlungen"),
    "tagsystem": ("Aktiv", "Futtertags"),
    "guestNumberFormat": ("YYYYNNN", "Format der Gastnummer"),
    "guestCardFormat": ("LP898", "Format der Gästekarte"),
    "guest_card_format": ("LP898", "Format der Gästekarte"),
    "locations": ("Aktiv", "Standorte"),
    "locationGuestAssigment": ("Aktiv", "Standortzuordnung von Gästen"),
    "foodplans": ("Aktiv", "Futterpläne"),
}


def ensure_default_settings() -> int:
    """Insert required settings without changing existing configuration."""
    existing_keys = {
        key
        for (key,) in db.session.query(Setting.setting_key)
        .filter(Setting.setting_key.in_(tuple(DEFAULT_SETTINGS)))
        .all()
    }
    missing_settings = [
        Setting(setting_key=key, value=value, description=description)
        for key, (value, description) in DEFAULT_SETTINGS.items()
        if key not in existing_keys
    ]
    if missing_settings:
        db.session.add_all(missing_settings)
        db.session.commit()
    return len(missing_settings)
