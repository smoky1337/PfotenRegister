import pytest
from datetime import datetime
from app.models import Guest
def test_register_animal_minimal(client,login):
    """Registriert ein Tier mit minimalen Pflichtfeldern."""
    guest_id = Guest.query.order_by(Guest.erstellt_am.desc()).offset(1).first().id
    login()


    # Minimaler Tier-Eintrag
    response = client.post("/guest/register/animal", data={
        "guest_id": guest_id,
        "art": "Hund",
        "tier_name": "Fifi",
        "kastriert": "ja",
        "futter": "Trocken",
        "vollversorgung": "nein",
        "active": "Aktiv"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Fifi".encode("utf-8") in response.data


def test_register_animal_maximal(client,login):
    """Registriert ein Tier mit allen möglichen Feldern."""
    heute = datetime.today().strftime('%Y-%m-%d')
    login()
    guest_id = Guest.query.order_by(Guest.erstellt_am.desc()).first().id
    # Maximaler Tier-Eintrag
    response = client.post("/guest/register/animal", data={
        "guest_id": guest_id,
        "art": "Katze",
        "rasse": "Perser",
        "tier_name": "Miezi",
        "tier_geschlecht": "F",
        "farbe": "Weiß",
        "kastriert": "ja",
        "identifikation": "CHIP-12345",
        "tier_geburtsdatum": "2015-04-04",
        "gewicht_groesse": "4kg",
        "krankheiten": "Asthma",
        "unvertraeglichkeiten": "Fisch",
        "futter": "Nass",
        "vollversorgung": "ja",
        "zuletzt_gesehen": heute,
        "tierarzt": "Dr. Katz",
        "futtermengeneintrag": "2kg Nassfutter",
        "steuerbescheid": "2025-12-31",
        "active": "Aktiv",
        "tier_notizen": "Braucht ruhigen Platz"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Miezi" in response.data