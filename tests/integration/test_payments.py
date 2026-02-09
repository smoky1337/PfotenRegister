import uuid

from werkzeug.security import generate_password_hash

from datetime import datetime

from app.models import Guest, Payment, User, db


def _create_user(username: str, password: str, role: str = "admin") -> None:
    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
        realname=username,
    )
    db.session.add(user)
    db.session.commit()


def _login(client, username: str, password: str) -> None:
    response = client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
    assert response.status_code == 200


def _bootstrap_login(client, app) -> None:
    username = f"admin-{uuid.uuid4().hex[:8]}"
    password = "admin"
    with app.app_context():
        _create_user(username, password)
    _login(client, username, password)


def _create_guest(client) -> str:
    unique_lastname = f"Pay-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/guest/register",
        data={
            "firstname": "Pay",
            "lastname": unique_lastname,
            "address": "Payweg 1",
            "city": "Kurzdorf",
            "zip": "00001",
            "email": "pay@pfotenregister.com",
            "indigence": "ALG",
            "status": "1",
            "action": "finish",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    return unique_lastname


def _get_guest_id(unique_lastname: str) -> str:
    guest = Guest.query.filter_by(lastname=unique_lastname).first()
    assert guest is not None
    return guest.id


def test_payment_list_view(client, app):
    _bootstrap_login(client, app)
    response = client.get("/payments/list", follow_redirects=True)
    assert response.status_code == 200
    assert "Zahlung".encode("utf-8") in response.data


def test_payment_create_direct_and_mark_paid(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    response = client.post(
        f"/payments/new_direct/{guest_id}/",
        data={
            "futter_betrag": "10.00",
            "zubehoer_betrag": "5.00",
            "kommentar": "Direktzahlung",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Zahlung erfolgreich erfasst".encode("utf-8") in response.data

    with app.app_context():
        payment = Payment.query.filter_by(guest_id=guest_id).order_by(Payment.id.desc()).first()
        assert payment is not None
        payment_id = payment.id
        assert payment.paid is False

    response = client.post(
        f"/payments/{payment_id}/mark_as_paid/",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Zahlung als bezahlt markiert".encode("utf-8") in response.data


def test_payment_offset(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        payment = Payment(
            guest_id=guest_id,
            created_on=datetime.now().date(),
            food_amount=12.00,
            other_amount=6.00,
            comment="Paid",
            paid=True,
            paid_on=datetime.now().date(),
        )
        db.session.add(payment)
        db.session.commit()
        payment_id = payment.id

    response = client.post(
        f"/payments/{payment_id}/create_offset",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Ausgleichszahlung erstellt".encode("utf-8") in response.data


def test_payment_delete_unpaid(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        payment = Payment(
            guest_id=guest_id,
            created_on=datetime.now().date(),
            food_amount=8.00,
            other_amount=0.00,
            comment="Open",
            paid=False,
            paid_on=None,
        )
        db.session.add(payment)
        db.session.commit()
        payment_id = payment.id

    response = client.post(
        f"/guest/{guest_id}/delete/{payment_id}",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Zahlung erfolreich gelöscht".encode("utf-8") in response.data

    with app.app_context():
        assert Payment.query.get(payment_id) is None


def test_payment_delete_paid_fails(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        payment = Payment(
            guest_id=guest_id,
            created_on=datetime.now().date(),
            food_amount=8.00,
            other_amount=0.00,
            comment="Paid",
            paid=True,
            paid_on=datetime.now().date(),
        )
        db.session.add(payment)
        db.session.commit()
        payment_id = payment.id

    response = client.post(
        f"/guest/{guest_id}/delete/{payment_id}",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "kann nicht mehr gelöscht".encode("utf-8") in response.data

    with app.app_context():
        assert Payment.query.get(payment_id) is not None
