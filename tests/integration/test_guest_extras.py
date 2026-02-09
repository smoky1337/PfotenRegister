import io
import uuid

from werkzeug.security import generate_password_hash

from app.models import Guest, User, db


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


def _bootstrap_login(client, app, role: str = "admin") -> None:
    username = f"{role}-{uuid.uuid4().hex[:8]}"
    password = "admin"
    with app.app_context():
        _create_user(username, password, role=role)
    _login(client, username, password)


def _create_guest(client) -> str:
    unique_lastname = f"Extra-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/guest/register",
        data={
            "firstname": "Extra",
            "lastname": unique_lastname,
            "address": "Extraw 1",
            "city": "Kurzdorf",
            "zip": "00001",
            "email": "extra@pfotenregister.com",
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


def test_guest_lookup_by_number(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest = _get_guest(unique_lastname)
        guest_number = guest.number

    response = client.get(f"/guest/lookup?guest_number={guest_number}", follow_redirects=False)
    assert response.status_code == 302
    assert f"/guest/{guest.id}" in response.headers.get("Location", "")


def test_guest_lookup_by_code(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest = _get_guest(unique_lastname)

    response = client.get(f"/guest/lookup?code={guest.id}", follow_redirects=False)
    assert response.status_code == 302
    assert f"/guest/{guest.id}" in response.headers.get("Location", "")


def test_guest_report(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest = _get_guest(unique_lastname)

    response = client.get(f"/guest/{guest.id}/report", follow_redirects=True)
    assert response.status_code == 200
    assert "Gastdaten".encode("utf-8") in response.data


def test_guest_print_card(client, app, monkeypatch):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest = _get_guest(unique_lastname)

    def _fake_pdf(_guest_ids, double_sided=True, flip_backside=False):
        return io.BytesIO(b"%PDF-1.4 test")

    monkeypatch.setattr("app.routes.guest_routes.generate_multiple_gast_cards_pdf", _fake_pdf)

    response = client.get(f"/guest/{guest.id}/print_card")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"


def test_guest_email_card_disabled(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest = _get_guest(unique_lastname)

    response = client.get(f"/guest/{guest.id}/email_card", follow_redirects=True)
    assert response.status_code == 200
    assert "E-Mail Versand ist deaktiviert".encode("utf-8") in response.data


def test_guest_email_card_enabled(client, app, monkeypatch):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest = _get_guest(unique_lastname)
        app.config["SETTINGS"]["emailEnabled"] = {"value": "Aktiv"}

    def _fake_send(_guest, _settings):
        return True, "OK"

    monkeypatch.setattr("app.routes.guest_routes.send_guest_card_email", _fake_send)

    response = client.get(f"/guest/{guest.id}/email_card", follow_redirects=True)
    assert response.status_code == 200
    assert "Gästekarte per E-Mail versendet".encode("utf-8") in response.data
