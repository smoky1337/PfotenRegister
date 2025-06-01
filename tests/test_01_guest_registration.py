import pytest
from datetime import datetime


def test_registriere_minimalen_gast(client,login):
    """Testet einen minimal gültigen Gast-Eintrag mit nur Pflichtfeldern."""
    login()
    heute = datetime.today().strftime('%Y-%m-%d')

    response = client.post("/guest/register", data={
        "vorname": "Mira",
        "nachname": "Kurz",
        "adresse": "Kurzweg 1",
        "ort": "Kurzdorf",
        "plz": "00001",
        "geburtsdatum": heute,
        "email": "kurz@pfotenregister.com",
        "beduerftigkeit": "ALG",
        "eintritt": heute,
        "status": "Aktiv",
        # Keine optionalen Felder
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Mira".encode("utf-8") in response.data


def test_registriere_maximalen_gast(client,login):
    """Testet einen vollständigen Gast-Eintrag mit allen möglichen Feldern."""
    login()

    heute = datetime.today().strftime('%Y-%m-%d')

    response = client.post("/guest/register", data={
        "vorname": "Max",
        "nachname": "Vollständig",
        "adresse": "Beispielstraße 1",
        "ort": "Teststadt",
        "plz": "12345",
        "festnetz": "0123-456789",
        "mobil": "0176-123456789",
        "email": "max@test.de",
        "geburtsdatum": "1970-12-01",
        "geschlecht": "Herr",
        "eintritt": heute,
        "austritt": "2026-01-01",
        "vertreter_name": "Vertretung Max",
        "vertreter_telefon": "0123-000000",
        "vertreter_email": "vertreter@test.de",
        "vertreter_adresse": "Vertretungsstraße 9",
        "status": "Aktiv",
        "beduerftigkeit": "Grundsicherung",
        "beduerftig_bis": "2025-12-31",
        "dokumente": "Bescheid gültig bis Ende 2025",
        "notizen": "Nimmt regelmäßig teil.",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Max".encode("utf-8") in response.data
