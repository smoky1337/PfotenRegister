import uuid
from datetime import date

from werkzeug.security import generate_password_hash

from app.models import AccessoriesHistory, Guest, User, db


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
    unique_lastname = f"Acc-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/guest/register",
        data={
            "firstname": "Acc",
            "lastname": unique_lastname,
            "address": "Accweg 1",
            "city": "Kurzdorf",
            "zip": "00001",
            "email": "acc@pfotenregister.com",
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


def test_accessory_create(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    response = client.post(
        f"/guest/{guest_id}/create_accessory",
        data={"item": "Leine", "comment": "Test"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Zubehör gespeichert".encode("utf-8") in response.data


def test_accessory_edit(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        entry = AccessoriesHistory(
            guest_id=guest_id,
            distributed_on=date.today(),
            item="Leine",
            comment="Alt",
        )
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    response = client.post(
        f"/accessory/{entry_id}/edit",
        data={"item": "Napf", "comment": "Neu"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Zubehör aktualisiert".encode("utf-8") in response.data


def test_accessory_delete(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        entry = AccessoriesHistory(
            guest_id=guest_id,
            distributed_on=date.today(),
            item="Leine",
            comment="Alt",
        )
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    response = client.post(
        f"/accessory/{entry_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Zubehör gelöscht".encode("utf-8") in response.data

    with app.app_context():
        assert AccessoriesHistory.query.get(entry_id) is None
