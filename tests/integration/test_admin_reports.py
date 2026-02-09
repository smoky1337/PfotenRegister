import io
import uuid
from datetime import date

from werkzeug.security import generate_password_hash

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
    unique_lastname = f"Rep-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/guest/register",
        data={
            "firstname": "Rep",
            "lastname": unique_lastname,
            "address": "Repweg 1",
            "city": "Kurzdorf",
            "zip": "00001",
            "email": "rep@pfotenregister.com",
            "indigence": "ALG",
            "status": "1",
            "action": "finish",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    return unique_lastname


def _get_guest(unique_lastname: str) -> Guest:
    guest = Guest.query.filter_by(lastname=unique_lastname).first()
    assert guest is not None
    return guest


def test_admin_export_transactions_view(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest = _get_guest(unique_lastname)
        db.session.add(
            Payment(
                guest_id=guest.id,
                created_on=date.today(),
                paid=True,
                paid_on=date.today(),
                food_amount=5.0,
                other_amount=2.0,
                comment="Test",
            )
        )
        db.session.commit()

    today = date.today().strftime("%Y-%m-%d")
    response = client.get(
        f"/admin/export_transactions?from={today}&to={today}",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Zahlungsbericht".encode("utf-8") in response.data


def test_admin_print_export_transactions(client, app, monkeypatch):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest = _get_guest(unique_lastname)
        db.session.add(
            Payment(
                guest_id=guest.id,
                created_on=date.today(),
                paid=True,
                paid_on=date.today(),
                food_amount=5.0,
                other_amount=2.0,
                comment="Test",
            )
        )
        db.session.commit()

    def _fake_report(_records, _from_dt, _to_dt):
        return io.BytesIO(b"pdf")

    monkeypatch.setattr("app.routes.admin.admin_routes.generate_payment_report", _fake_report)

    today = date.today().strftime("%d.%m.%Y")
    response = client.get(
        f"/admin/print_export_transactions?from_date={today}&to_date={today}",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"


def test_admin_guest_cards_view(client, app):
    _bootstrap_login(client, app)
    response = client.get("/admin/guest_cards", follow_redirects=True)
    assert response.status_code == 200
    assert "Gästekarten".encode("utf-8") in response.data


def test_admin_print_guest_cards_pdf(client, app, monkeypatch):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest = _get_guest(unique_lastname)

    def _fake_cards(_guest_ids, double_sided=True, flip_backside=False):
        return io.BytesIO(b"%PDF-1.4 test")

    monkeypatch.setattr("app.routes.admin.admin_routes.generate_multiple_gast_cards_pdf", _fake_cards)

    response = client.post(
        "/admin/print_guest_cards",
        data={"guest_ids": [guest.id]},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"


def test_admin_print_guest_cards_email_disabled(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest = _get_guest(unique_lastname)

    response = client.post(
        "/admin/print_guest_cards",
        data={"guest_ids": [guest.id], "action": "email"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "E-Mail Versand ist deaktiviert".encode("utf-8") in response.data
