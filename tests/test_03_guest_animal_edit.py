import re
from datetime import datetime

from app import db_cursor


def test_update_guest(client, login):
    login()

    # Hole den zuletzt erstellten Gast
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM gaeste ORDER BY erstellt_am DESC LIMIT 1")
        guest = cursor.fetchone()
        guest_id = guest["id"]

    # Bearbeite den Gast (z. B. Adresse ändern, Rest beibehalten)
    response = client.post(f"/guest/{guest_id}/update", data={
        "vorname": guest["vorname"],
        "nachname": guest["nachname"],
        "nummer": guest["nummer"],
        "adresse": "Langweg 23",
        "plz": guest["plz"],
        "ort": guest["ort"],
        "festnetz": guest["festnetz"] or "",
        "mobil": guest["mobil"] or "",
        "email": guest["email"] or "",
        "geburtsdatum": guest["geburtsdatum"],
        "geschlecht": guest["geschlecht"],
        "eintritt": guest["eintritt"],
        "austritt": guest["austritt"] or "",
        "vertreter_name": guest["vertreter_name"] or "",
        "vertreter_telefon": guest["vertreter_telefon"] or "",
        "vertreter_email": guest["vertreter_email"] or "",
        "vertreter_adresse": guest["vertreter_adresse"] or "",
        "status": guest["status"],
        "beduerftigkeit": guest["beduerftigkeit"] or "",
        "beduerftig_bis": guest["beduerftig_bis"] or "",
        "dokumente": guest["dokumente"] or "",
        "notizen": guest["notizen"] or ""
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Langweg 23".encode("utf-8") in response.data


def test_update_animal(client, login):
    login()
    # Hole den zuletzt erstellten Gast
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM gaeste ORDER BY erstellt_am DESC LIMIT 1")
        guest_id = cursor.fetchone()["id"]

    # Hole das zugehörige Tier
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM tiere WHERE gast_id = %s ORDER BY erstellt_am DESC LIMIT 1", (guest_id,))
        tier = cursor.fetchone()
        animal_id = tier["id"]

    # Bearbeite das Tier (z. B. Name ändern, Rest beibehalten)
    response = client.post(f"/guest/{guest_id}/{animal_id}/update", data={
        "art": tier["art"],
        "rasse": tier["rasse"] or "",
        "tier_name": "NEUER NAME",
        "tier_geschlecht": tier["geschlecht"] or "",
        "farbe": tier["farbe"] or "",
        "kastriert": tier["kastriert"],
        "identifikation": tier["identifikation"] or "",
        "tier_geburtsdatum": tier["geburtsdatum"] or "",
        "gewicht_groesse": tier["gewicht_oder_groesse"] or "",
        "krankheiten": tier["krankheiten"] or "",
        "unvertraeglichkeiten": tier["unvertraeglichkeiten"] or "",
        "futter": tier["futter"],
        "vollversorgung": tier["vollversorgung"],
        "zuletzt_gesehen": tier["zuletzt_gesehen"] or "",
        "tierarzt": tier["tierarzt"] or "",
        "futtermengeneintrag": tier["futtermengeneintrag"] or "",
        "tier_notizen": tier["notizen"] or ""
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "NEUER NAME".encode("utf-8") in response.data

import pytest
from app import db_cursor

def test_edit_guest_notes(client, login):
    """Testet das Aktualisieren der Notizen eines Gastes."""
    login()

    # Hole den zuletzt erstellten Gast
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM gaeste ORDER BY erstellt_am DESC LIMIT 1")
        guest_id = cursor.fetchone()["id"]

    neue_notiz = "Testnotiz für Gast"
    response = client.post(f"/guest/{guest_id}/edit_notes", data={
        "notizen": neue_notiz
    }, follow_redirects=True)

    assert response.status_code == 200
    assert neue_notiz.encode("utf-8") in response.data


def test_edit_animal_notes(client, login):
    """Testet das Aktualisieren der Notizen eines Tiers."""
    login()

    # Hole den zuletzt erstellten Gast
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM gaeste ORDER BY erstellt_am DESC LIMIT 1")
        guest_id = cursor.fetchone()["id"]

    # Hole das zuletzt erstellte Tier dieses Gastes
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM tiere WHERE gast_id = %s ORDER BY erstellt_am DESC LIMIT 1", (guest_id,))
        tier_id = cursor.fetchone()["id"]

    neue_notiz = "Testnotiz für Tier"
    response = client.post(f"/guest/{guest_id}/edit_animal_notes/{tier_id}", data={
        "notizen": neue_notiz
    }, follow_redirects=True)

    assert response.status_code == 200
    assert neue_notiz.encode("utf-8") in response.data