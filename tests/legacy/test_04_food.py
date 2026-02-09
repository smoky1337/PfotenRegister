import re
from datetime import datetime

from app.models import Guest, FoodHistory, db

def test_food_distribution(client, login):
    """Testet die kombinierte Futtervergabe und Zahlung."""
    login()

    # Letzten Gast holen
    guest_id = Guest.query.order_by(Guest.created_on.desc()).first().id

    response = client.post(f"/guest/{guest_id}/create_food_entry", data={
        "notiz": "Testausgabe mit Kommentar",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Futterverteilung gespeichert.".encode("utf-8") in response.data

def test_edit_and_delete_feed_entry(client, login):
    login()

    # Gast-ID holen
    guest_id = Guest.query.order_by(Guest.created_on.desc()).first().id

    # Eintrag erzeugen
    entry = FoodHistory(guest_id=guest_id, distributed_on=datetime.today().date(), comment="ursprüngliche Notiz")
    db.session.add(entry)
    db.session.commit()
    id = entry.id

    # --- Bearbeiten ---
    response = client.post(f"/feed_entry/{id}/edit", data={
        "futtertermin": datetime.today().date(),
        "notiz": "bearbeitete Notiz"

    }, follow_redirects=True)

    assert response.status_code == 200
    updated = FoodHistory.query.get(id)
    assert updated.comment == "bearbeitete Notiz"

    # --- Löschen ---
    response = client.post(f"/feed_entry/{id}/delete", follow_redirects=True)
    assert response.status_code == 200
    assert FoodHistory.query.get(id) is None
