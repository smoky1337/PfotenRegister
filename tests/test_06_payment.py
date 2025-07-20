from datetime import datetime

from app.models import Guest, Payments


def test_food_distribution(client, login):
    """Testet die kombinierte Futtervergabe und Zahlung."""
    login()

    # Letzten Gast holen
    guest_id = Guest.query.order_by(Guest.created_on.desc()).first().id

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
    guest_id = Guest.query.order_by(Guest.created_on.desc()).first().id

    today = datetime.today().strftime("%Y-%m-%d")
    response = client.post(f"/payments/new_direct/{guest_id}", data={
        "futter_betrag": "10.00",
        "zubehoer_betrag": "5.00",
        "kommentar": f"Direktzahlung am {today}",
        "bezahlt": None
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Zahlung erfolgreich erfasst.".encode("utf-8") in response.data


def test_mark_as_paid_payment(client, login):
    """Test marking an existing payment as paid."""
    login()
    payment = Payments.query.order_by(Payments.id.desc()).first()
    guest_id = payment.guest_id
    today_str = datetime.today().strftime("%Y-%m-%d")
    # Create a paid payment
    client.post(f"/payments/new_direct/{guest_id}/", data={
        "futter_betrag": "12.00",
        "zubehoer_betrag": "6.00",
        "kommentar": f"Paid test {today_str}",
        "bezahlt": False
    }, follow_redirects=True)
    payment = Payments.query.filter_by(guest_id=guest_id).order_by(Payments.id.desc()).first()
    assert not payment.paid

    # Mark payment as paid
    response = client.post(
        f"/payments/{payment.id}/mark_as_paid/",
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Zahlung als bezahlt markiert." in response.data

    # Verify paid flag and date
    updated = Payments.query.get(payment.id)
    assert updated.paid
    assert updated.paid_on.strftime("%Y-%m-%d") == today_str


def test_create_offset_payment(client, login):
    """Test creating a reverse payment (offset)."""
    login()
    payment = Payments.query.order_by(Payments.id.desc()).first()
    guest_id = payment.guest_id
    today_str = datetime.today().strftime("%Y-%m-%d")
    # Create a paid payment
    client.post(f"/payments/new_direct/{guest_id}/", data={
        "futter_betrag": "12.00",
        "zubehoer_betrag": "6.00",
        "kommentar": f"Paid test {today_str}",
        "bezahlt": True
    }, follow_redirects=True)
    payment = Payments.query.filter_by(guest_id=guest_id).order_by(Payments.id.desc()).first()
    assert payment.paid
    orig_food = payment.food_amount
    orig_other = payment.other_amount

    # Create offset payment
    response = client.post(
        f"/payments/{payment.id}/create_offset",
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Ausgleichszahlung erstellt." in response.data

    # Verify offset entry exists and is paid
    offset = Payments.query.filter_by(
        guest_id=guest_id,
        food_amount=-orig_food,
        other_amount=-orig_other
    ).first()
    assert offset is not None
    assert offset.paid

