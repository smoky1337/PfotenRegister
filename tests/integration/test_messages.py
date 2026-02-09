import uuid
from datetime import date

from werkzeug.security import generate_password_hash

from app.models import Guest, Message, User, db


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
    unique_lastname = f"Msg-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/guest/register",
        data={
            "firstname": "Msg",
            "lastname": unique_lastname,
            "address": "Msgweg 1",
            "city": "Kurzdorf",
            "zip": "00001",
            "email": "msg@pfotenregister.com",
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


def test_message_create(client, app):
    _bootstrap_login(client, app, role="admin")
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    response = client.post(
        f"/guest/{guest_id}/add_message",
        data={"message": "Bitte nachreichen"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Nachricht hinterlegt".encode("utf-8") in response.data


def test_message_complete_json(client, app):
    _bootstrap_login(client, app, role="admin")
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        user = User.query.filter(User.username.like("admin-%")).first()
        msg = Message(
            guest_id=guest_id,
            created_by=user.id,
            created_on=date.today(),
            content="Bitte nachreichen",
        )
        db.session.add(msg)
        db.session.commit()
        message_id = msg.id

    response = client.post(
        f"/guest/{guest_id}/message/{message_id}/complete",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True


def test_message_list_view(client, app):
    _bootstrap_login(client, app, role="admin")
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        user = User.query.filter(User.username.like("admin-%")).first()
        msg = Message(
            guest_id=guest_id,
            created_by=user.id,
            created_on=date.today(),
            content="Bitte nachreichen",
        )
        db.session.add(msg)
        db.session.commit()

    response = client.get("/messages/list", follow_redirects=True)
    assert response.status_code == 200
    assert "Bitte nachreichen".encode("utf-8") in response.data
