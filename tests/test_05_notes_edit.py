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