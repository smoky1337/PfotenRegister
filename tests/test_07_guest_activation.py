from app.models import Guest


def test_guest_deactivation(client, login):
    """Deaktiviert einen aktiven Gast."""
    login()

    row = Guest.query.order_by(Guest.created_on.desc()).first()
    guest_id = row.id

    # Deaktivieren
    response = client.post(f"/guest/{guest_id}/deactivate", follow_redirects=True)

    assert response.status_code == 200
    assert "deaktiviert".encode("utf-8") in response.data

    # Optional: Prüfen, ob Gast jetzt inaktiv ist
    status = Guest.query.get(guest_id).status
    assert status == False


def test_guest_activation(client, login):
    """Aktiviert einen inaktiven Gast."""
    login()

    row = Guest.query.order_by(Guest.created_on.desc()).first()
    guest_id = row.id

    # Aktivieren
    response = client.post(f"/guest/{guest_id}/activate", follow_redirects=True)

    assert response.status_code == 200
    assert "aktiviert".encode("utf-8") in response.data

    # Optional: Prüfen, ob Gast jetzt aktiv ist
    status = Guest.query.get(guest_id).status
    assert status == True