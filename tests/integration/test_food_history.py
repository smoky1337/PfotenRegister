import uuid
from datetime import date

from werkzeug.security import generate_password_hash

from app.models import FoodHistory, Guest, User, db


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
    unique_lastname = f"Food-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/guest/register",
        data={
            "firstname": "Food",
            "lastname": unique_lastname,
            "address": "Foodweg 1",
            "city": "Kurzdorf",
            "zip": "00001",
            "email": "food@pfotenregister.com",
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


def test_food_entry_create(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    response = client.post(
        f"/guest/{guest_id}/create_food_entry",
        data={"notiz": "Testausgabe"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Futterverteilung gespeichert".encode("utf-8") in response.data


def test_food_entry_edit(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        entry = FoodHistory(
            guest_id=guest_id,
            distributed_on=date.today(),
            comment="Alt",
        )
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    response = client.post(
        f"/feed_entry/{entry_id}/edit",
        data={
            "notiz": "Neu",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_food_entry_delete(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        entry = FoodHistory(
            guest_id=guest_id,
            distributed_on=date.today(),
            comment="Alt",
        )
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    response = client.post(
        f"/feed_entry/{entry_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Futtereintrag gelöscht".encode("utf-8") in response.data

    with app.app_context():
        assert FoodHistory.query.get(entry_id) is None
