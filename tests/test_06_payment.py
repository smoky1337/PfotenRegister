from datetime import datetime
from app.models import Guest


def test_food_distribution(client, login):
    """Testet die kombinierte Futtervergabe und Zahlung."""
    login()

    # Letzten Gast holen
    guest_id = Guest.query.order_by(Guest.erstellt_am.desc()).first().id

    response = client.post(f"/guest/{guest_id}/create_food_entry", data={
        "notiz": "Testausgabe mit Kommentar",
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
    guest_id = Guest.query.order_by(Guest.erstellt_am.desc()).first().id

    today = datetime.today().strftime("%Y-%m-%d")
    response = client.post(f"/guest/{guest_id}/payment_direct", data={
        "futter_betrag": "10.00",
        "zubehoer_betrag": "5.00",
        "kommentar": f"Direktzahlung am {today}"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Zahlung erfolgreich erfasst.".encode("utf-8") in response.data