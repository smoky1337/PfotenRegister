import io
import uuid
from datetime import date

from werkzeug.security import generate_password_hash

from app.models import Attachment, Animal, Guest, User, db


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
    unique_lastname = f"Att-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/guest/register",
        data={
            "firstname": "Att",
            "lastname": unique_lastname,
            "address": "Attweg 1",
            "city": "Kurzdorf",
            "zip": "00001",
            "email": "att@pfotenregister.com",
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


def test_attachment_upload(client, app, monkeypatch):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    def _fake_upload_file(file_storage, owner_id: str) -> str:
        return f"guest/{owner_id}/test.txt"

    monkeypatch.setattr("app.routes.attachement_routes.upload_file", _fake_upload_file)

    data = {
        "file": (io.BytesIO(b"test"), "test.txt"),
    }
    response = client.post(
        f"/attachment/{guest_id}/upload",
        data=data,
        content_type="multipart/form-data",
        headers={"Referer": f"/guest/{guest_id}"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Datei erfolgreich hochgeladen".encode("utf-8") in response.data


def test_attachment_download(client, app, monkeypatch):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        att = Attachment(
            owner_id=guest_id,
            filename="test.txt",
            gcs_path="guest/test/test.txt",
            uploaded_on=date.today(),
        )
        db.session.add(att)
        db.session.commit()
        att_id = att.id

    class _FakeBlob:
        content_type = "text/plain"

        def download_as_bytes(self):
            return b"test"

    class _FakeBucket:
        def blob(self, _path):
            return _FakeBlob()

    with app.app_context():
        app.bucket = _FakeBucket()

    response = client.get(f"/attachment/{att_id}/download")
    assert response.status_code == 200
    assert response.data == b"test"


def test_attachment_delete(client, app, monkeypatch):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        att = Attachment(
            owner_id=guest_id,
            filename="test.txt",
            gcs_path="guest/test/test.txt",
            uploaded_on=date.today(),
        )
        db.session.add(att)
        db.session.commit()
        att_id = att.id

    def _fake_delete_blob(_path: str) -> None:
        return None

    monkeypatch.setattr("app.routes.attachement_routes.delete_blob", _fake_delete_blob)

    response = client.post(
        f"/attachment/{att_id}/delete",
        headers={"Referer": f"/guest/{guest_id}"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Datei gelöscht".encode("utf-8") in response.data

    with app.app_context():
        assert Attachment.query.get(att_id) is None


def test_attachment_list(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        att = Attachment(
            owner_id=guest_id,
            filename="test.txt",
            gcs_path="guest/test/test.txt",
            uploaded_on=date.today(),
        )
        db.session.add(att)
        db.session.commit()

    response = client.get("/attachment/list", follow_redirects=True)
    assert response.status_code == 200
    assert "test.txt".encode("utf-8") in response.data


def test_attachment_set_animal_picture(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    _create_animal(client, guest_id, "PicTier")

    with app.app_context():
        animal = Animal.query.filter_by(guest_id=guest_id).order_by(Animal.id.desc()).first()
        assert animal is not None
        animal_id = animal.id
        att = Attachment(
            owner_id=guest_id,
            filename="test.txt",
            gcs_path="guest/test/test.txt",
        )
        db.session.add(att)
        db.session.commit()
        att_id = att.id

    response = client.post(
        f"/attachment/set_animal_picture/{animal_id}",
        data={"attachment_id": str(att_id)},
        headers={"Referer": f"/guest/{guest_id}"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        animal = Animal.query.get(animal_id)
        assert animal is not None
        assert str(animal.profile_attachment_id) == str(att_id)


def test_attachment_remove_animal_picture(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    _create_animal(client, guest_id, "PicTier")

    with app.app_context():
        animal = Animal.query.filter_by(guest_id=guest_id).order_by(Animal.id.desc()).first()
        assert animal is not None
        animal.profile_attachment_id = None
        db.session.commit()
        animal_id = animal.id

    response = client.post(
        f"/attachment/remove_animal_picture/{animal_id}",
        headers={"Referer": f"/guest/{guest_id}"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Profilbild entfernt".encode("utf-8") in response.data
