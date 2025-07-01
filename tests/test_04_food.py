import re
from datetime import datetime

from app.models import Guest, FoodHistory, db

def test_food_distribution(client, login):
    """Testet die kombinierte Futtervergabe und Zahlung."""
    login()

    # Letzten Gast holen
    guest_id = Guest.query.order_by(Guest.erstellt_am.desc()).first().id

    response = client.post(f"/guest/{guest_id}/create_food_entry", data={
        "comment": "Testausgabe mit Kommentar",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Futterverteilung gespeichert.".encode("utf-8") in response.data

def test_edit_and_delete_feed_entry(client, login):
    login()

    # Gast-ID holen
    guest_id = Guest.query.order_by(Guest.erstellt_am.desc()).first().id

    # Eintrag erzeugen
    entry = FoodHistory(gast_id=guest_id, futtertermin=datetime.today().date(), notiz="ursprüngliche Notiz")
    db.session.add(entry)
    db.session.commit()
    entry_id = entry.entry_id

    # --- Bearbeiten ---
    response = client.post(f"/feed_entry/{entry_id}/edit", data={
        "futtertermin": datetime.today().date().isoformat(),
        "notiz": "bearbeitete Notiz"
    }, follow_redirects=True)

    assert response.status_code == 200
    updated = FoodHistory.query.get(entry_id)
    assert updated.notiz == "bearbeitete Notiz"

    # --- Löschen ---
    response = client.post(f"/feed_entry/{entry_id}/delete", follow_redirects=True)
    assert response.status_code == 200
    assert FoodHistory.query.get(entry_id) is None
