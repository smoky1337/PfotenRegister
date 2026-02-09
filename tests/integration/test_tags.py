import uuid

from werkzeug.security import generate_password_hash

from app.models import Animal, FoodTag, Guest, User, db


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
    unique_lastname = f"Tag-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/guest/register",
        data={
            "firstname": "Tag",
            "lastname": unique_lastname,
            "address": "Tagweg 1",
            "city": "Kurzdorf",
            "zip": "00001",
            "email": "tag@pfotenregister.com",
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


def test_admin_food_tags_create(client, app):
    _bootstrap_login(client, app, role="admin")

    response = client.post(
        "/admin/food_tags",
        data={
            "new_name[]": ["TestTag"],
            "new_color[]": ["#ff0000"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Foodtags wurden aktualisiert".encode("utf-8") in response.data

    with app.app_context():
        tag = FoodTag.query.filter_by(name="TestTag").first()
        assert tag is not None
        assert tag.color == "#ff0000"


def test_admin_food_tags_update(client, app):
    _bootstrap_login(client, app, role="admin")

    with app.app_context():
        tag = FoodTag(name="TestTag", color="#ff0000")
        db.session.add(tag)
        db.session.commit()
        tag_id = tag.id

    response = client.post(
        "/admin/food_tags",
        data={
            f"name_{tag_id}": "TestTag2",
            f"color_{tag_id}": "#00ff00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        tag = FoodTag.query.get(tag_id)
        assert tag is not None
        assert tag.name == "TestTag2"
        assert tag.color == "#00ff00"


def test_admin_food_tags_delete(client, app):
    _bootstrap_login(client, app, role="admin")

    with app.app_context():
        tag = FoodTag(name="TestTag", color="#ff0000")
        db.session.add(tag)
        db.session.commit()
        tag_id = tag.id

    response = client.post(
        "/admin/food_tags",
        data={
            f"delete_{tag_id}": "1",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        assert FoodTag.query.get(tag_id) is None


def test_animal_edit_tags(client, app):
    _bootstrap_login(client, app, role="admin")
    unique_lastname = _create_guest(client)

    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    _create_animal(client, guest_id, "TagTier")

    with app.app_context():
        animal = Animal.query.filter_by(guest_id=guest_id).order_by(Animal.id.desc()).first()
        assert animal is not None
        animal_id = animal.id
        tag = FoodTag(name="TestTag", color="#ff0000")
        db.session.add(tag)
        db.session.commit()
        tag_id = tag.id

    response = client.post(
        f"/animals/{animal_id}/edit_tags",
        data={"tag_ids": [str(tag_id)]},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Tags aktualisiert".encode("utf-8") in response.data

    with app.app_context():
        animal = Animal.query.get(animal_id)
        assert animal is not None
        assert any(t.id == tag_id for t in animal.food_tags)
