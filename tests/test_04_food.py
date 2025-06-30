import re
from datetime import datetime

from app import db_cursor

def test_food_distribution(client, login):
    """Testet die kombinierte Futtervergabe und Zahlung."""
    login()

    # Letzten Gast holen
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM gaeste ORDER BY erstellt_am DESC LIMIT 1")
        guest_id = cursor.fetchone()["id"]

    response = client.post(f"/guest/{guest_id}/create_food_entry", data={
        "comment": "Testausgabe mit Kommentar",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Futterverteilung gespeichert.".encode("utf-8") in response.data

def test_edit_and_delete_feed_entry(client, login):
    login()

    with db_cursor() as cursor:
        # Gast-ID holen
        cursor.execute("SELECT id FROM gaeste ORDER BY erstellt_am DESC LIMIT 1")
        guest_id = cursor.fetchone()["id"]

        # Eintrag erzeugen
        cursor.execute("""
            INSERT INTO futterhistorie (gast_id, futtertermin, notizen)
            VALUES (%s, %s, %s) RETURNING entry_id
        """, (guest_id, datetime.today().date(), "ursprüngliche Notiz"))
        entry_id = cursor.fetchone()["entry_id"]

    # --- Bearbeiten ---
    response = client.post(f"/feed_entry/{entry_id}/edit", data={
        "futtertermin": datetime.today().date().isoformat(),
        "notiz": "bearbeitete Notiz"
    }, follow_redirects=True)

    assert response.status_code == 200
    with db_cursor() as cursor:
        cursor.execute("SELECT notizen FROM futterhistorie WHERE entry_id = %s", (entry_id,))
        updated = cursor.fetchone()
        assert updated["notiz"] == "bearbeitete Notiz"

    # --- Löschen ---
    response = client.post(f"/feed_entry/{entry_id}/delete", follow_redirects=True)
    assert response.status_code == 200
    with db_cursor() as cursor:
        cursor.execute("SELECT entry_id FROM futterhistorie WHERE entry_id = %s", (entry_id,))
        assert cursor.fetchone() is None
