import pytest
from datetime import datetime
from app.db import db_cursor
def test_register_animal_minimal(client,login):
    """Registriert ein Tier mit minimalen Pflichtfeldern."""
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM gaeste ORDER BY erstellt_am DESC LIMIT 2")
        rows = cursor.fetchall()
        guest_id = rows[1]["id"]  # vorletzter Gast
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
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM gaeste ORDER BY erstellt_am DESC LIMIT 1")
        guest_id = cursor.fetchone()["id"]  # letzter Gast
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