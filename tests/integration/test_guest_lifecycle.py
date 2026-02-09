import uuid
from datetime import date

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


def _bootstrap_login(client, app) -> None:
    username = f"admin-{uuid.uuid4().hex[:8]}"
    password = "admin"
    with app.app_context():
        _create_user(username, password)
    _login(client, username, password)


def _create_guest(client) -> str:
    unique_lastname = f"Test-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/guest/register",
        data={
            "firstname": "Kurz",
            "lastname": unique_lastname,
            "address": "Kurzweg 1",
            "city": "Kurzdorf",
            "zip": "00001",
            "email": "kurz@pfotenregister.com",
            "indigence": "ALG",
            "status": "1",
            "action": "finish",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert unique_lastname.encode("utf-8") in response.data
    return unique_lastname


def _get_guest_snapshot(unique_lastname: str) -> dict:
    guest = Guest.query.filter_by(lastname=unique_lastname).first()
    assert guest is not None
    return {
        "id": guest.id,
        "number": guest.number or "",
        "gender": guest.gender or "",
        "member_since": guest.member_since.isoformat() if guest.member_since else "",
        "status": guest.status or "",
        "indigence": guest.indigence or "",
    }


def test_guest_create(client, app):
    _bootstrap_login(client, app)
    _create_guest(client)


def test_guest_view(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_snapshot(unique_lastname)["id"]

    response = client.get(f"/guest/{guest_id}", follow_redirects=True)
    assert response.status_code == 200
    assert unique_lastname.encode("utf-8") in response.data


def test_guest_edit_page(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_snapshot(unique_lastname)["id"]

    response = client.get(f"/guest/{guest_id}/edit", follow_redirects=True)
    assert response.status_code == 200
    assert "Gast bearbeiten".encode("utf-8") in response.data


def test_guest_edit(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)

    with app.app_context():
        snapshot = _get_guest_snapshot(unique_lastname)
        guest_id = snapshot["id"]

    response = client.post(
        f"/guest/{guest_id}/update",
        data={
            "firstname": "Kurz",
            "lastname": unique_lastname,
            "number": snapshot["number"],
            "address": "Langweg 23",
            "zip": "00001",
            "city": "Kurzdorf",
            "phone": "",
            "mobile": "",
            "email": "kurz@pfotenregister.com",
            "gender": snapshot["gender"],
            "member_since": snapshot["member_since"],
            "member_until": "",
            "r_name": "",
            "r_phone": "",
            "r_email": "",
            "r_address": "",
            "status": snapshot["status"],
            "indigence": snapshot["indigence"],
            "indigent_until": "",
            "documents": "",
            "notes": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Langweg 23".encode("utf-8") in response.data


def test_guest_deactivate(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_snapshot(unique_lastname)["id"]

    response = client.post(f"/guest/{guest_id}/deactivate", follow_redirects=True)
    assert response.status_code == 200
    assert "deaktiviert".encode("utf-8") in response.data


def test_guest_activate(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_snapshot(unique_lastname)["id"]

    response = client.post(f"/guest/{guest_id}/activate", follow_redirects=True)
    assert response.status_code == 200
    assert "aktiviert".encode("utf-8") in response.data


def test_guest_delete(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_snapshot(unique_lastname)["id"]

    response = client.post(f"/guest/{guest_id}/delete", follow_redirects=True)
    assert response.status_code == 200
    assert "Gast wurde vollständig gelöscht".encode("utf-8") in response.data

    with app.app_context():
        assert Guest.query.get(guest_id) is None
