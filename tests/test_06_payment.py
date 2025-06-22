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
        "futter_betrag": "5.50",
        "zubehoer_betrag": "2.00",
        "zahlungKommentar_futter": "Kleine Zahlung"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Futterverteilung und Zahlung gespeichert.".encode("utf-8") in response.data


def test_direct_payment(client, login):
    """Testet das manuelle Hinzufügen eines Zahlungseintrags."""
    login()

    # Letzten Gast holen
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM gaeste ORDER BY erstellt_am DESC LIMIT 1")
        guest_id = cursor.fetchone()["id"]

    today = datetime.today().strftime("%Y-%m-%d")
    response = client.post(f"/guest/{guest_id}/payment_direct", data={
        "futter_betrag": "10.00",
        "zubehoer_betrag": "5.00",
        "kommentar": f"Direktzahlung am {today}"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Zahlung erfolgreich erfasst.".encode("utf-8") in response.data