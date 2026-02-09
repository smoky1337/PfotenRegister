import uuid

from werkzeug.security import generate_password_hash

from app.models import Animal, Guest, User, db


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
    return unique_lastname


def _get_guest_id(unique_lastname: str) -> str:
    guest = Guest.query.filter_by(lastname=unique_lastname).first()
    assert guest is not None
    return guest.id


def _create_animal(client, guest_id: str, name: str) -> None:
    response = client.post(
        "/animals/register",
        data={
            "guest_id": guest_id,
            "species": "Hund",
            "name": name,
            "castrated": "Ja",
            "food_type": "Trocken",
            "complete_care": "Unbekannt",
            "status": "1",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert name.encode("utf-8") in response.data


def test_animal_create(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    name = f"Fifi-{uuid.uuid4().hex[:6]}"
    _create_animal(client, guest_id, name)


def test_animal_edit(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    name = f"Fifi-{uuid.uuid4().hex[:6]}"
    _create_animal(client, guest_id, name)

    with app.app_context():
        animal = Animal.query.filter_by(guest_id=guest_id).order_by(Animal.id.desc()).first()
        assert animal is not None
        animal_id = animal.id

    response = client.post(
        f"/animals/{animal_id}/update",
        data={
            "name": "NEUER NAME",
            "species": "Hund",
            "status": "1",
            "castrated": "Ja",
            "food_type": "Trocken",
            "complete_care": "Unbekannt",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "NEUER NAME".encode("utf-8") in response.data


def test_animal_notes(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    name = f"Fifi-{uuid.uuid4().hex[:6]}"
    _create_animal(client, guest_id, name)

    with app.app_context():
        animal = Animal.query.filter_by(guest_id=guest_id).order_by(Animal.id.desc()).first()
        assert animal is not None
        animal_id = animal.id

    response = client.post(
        f"/animals/{animal_id}/edit_note",
        data={"notizen": "Testnotiz für Tier"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Testnotiz".encode("utf-8") in response.data


def test_animal_delete(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    name = f"Fifi-{uuid.uuid4().hex[:6]}"
    _create_animal(client, guest_id, name)

    with app.app_context():
        animal = Animal.query.filter_by(guest_id=guest_id).order_by(Animal.id.desc()).first()
        assert animal is not None
        animal_id = animal.id

    response = client.post(
        f"/animals/{animal_id}/delete",
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        assert Animal.query.get(animal_id) is None
