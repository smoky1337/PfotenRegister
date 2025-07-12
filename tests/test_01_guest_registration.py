import pytest
from datetime import datetime


def test_registriere_minimalen_gast(client,login):
    """Testet einen minimal gültigen Gast-Eintrag mit nur Pflichtfeldern."""
    login()
    today = datetime.today().strftime('%Y-%m-%d')

    response = client.post("/guest/register", data={
        "firstname": "Kurz",
        "lastname": "Test",
        "address": "Kurzweg 1",
        "city": "Kurzdorf",
        "zip": "00001",
        "birthdate": today,
        "email": "kurz@pfotenregister.com",
        "indigence": "ALG",
        "member_since": today,
        "status": "1",

    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Kurz".encode("utf-8") in response.data


def test_registriere_maximalen_gast(client,login):
    """Testet einen vollständigen Gast-Eintrag mit allen möglichen Feldern."""
    login()

    heute = datetime.today().strftime('%Y-%m-%d')

    response = client.post("/guest/register", data={
        "firstname": "Max",
        "lastname": "Vollständig",
        "address": "Beispielstraße 1",
        "city": "Teststadt",
        "zip": "12345",
        "phone": "0123-456789",
        "mobile": "0176-123456789",
        "email": "max@test.de",
        "birthdate": "1970-12-01",
        "gender": "Mann",
        "member_since": heute,
        "member_until": "2026-01-01",
        "r_name": "Vertretung Max",
        "r_phone": "0123-000000",
        "r_email": "vertreter@test.de",
        "r_address": "Vertretungsstraße 9",
        "status": "1",
        "indigence": "Grundsicherung",
        "indigent_until": "2025-12-31",
        "documents": "Bescheid gültig bis Ende 2025",
        "notes": "Nimmt regelmäßig teil.",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Vollständig".encode("utf-8") in response.data
