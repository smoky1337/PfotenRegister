from app import db_cursor


def test_guest_deactivation(client, login):
    """Deaktiviert einen aktiven Gast."""
    login()

    with db_cursor() as cursor:
        cursor.execute("SELECT id, status FROM gaeste ORDER BY erstellt_am DESC LIMIT 1")
        row = cursor.fetchone()
        guest_id = row["id"]

    # Deaktivieren
    response = client.post(f"/guest/{guest_id}/deactivate", follow_redirects=True)

    assert response.status_code == 200
    assert "deaktiviert".encode("utf-8") in response.data

    # Optional: Prüfen, ob Gast jetzt inaktiv ist
    with db_cursor() as cursor:
        cursor.execute("SELECT status FROM gaeste WHERE id = %s", (guest_id,))
        status = cursor.fetchone()["status"]
    assert status == "Inaktiv"


def test_guest_activation(client, login):
    """Aktiviert einen inaktiven Gast."""
    login()

    with db_cursor() as cursor:
        cursor.execute("SELECT id, status FROM gaeste ORDER BY erstellt_am DESC LIMIT 1")
        row = cursor.fetchone()
        guest_id = row["id"]

    # Aktivieren
    response = client.post(f"/guest/{guest_id}/activate", follow_redirects=True)

    assert response.status_code == 200
    assert "aktiviert".encode("utf-8") in response.data

    # Optional: Prüfen, ob Gast jetzt aktiv ist
    with db_cursor() as cursor:
        cursor.execute("SELECT status FROM gaeste WHERE id = %s", (guest_id,))
        status = cursor.fetchone()["status"]
    assert status == "Aktiv"