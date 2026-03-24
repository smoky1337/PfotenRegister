import uuid
from datetime import date

from werkzeug.security import generate_password_hash

from app.models import Attachment, Animal, Guest, MedicalEvent, MedicalEventAttachment, User, db


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
    unique_lastname = f"Medical-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/guest/register",
        data={
            "firstname": "Medical",
            "lastname": unique_lastname,
            "address": "Tierweg 1",
            "city": "Kurzdorf",
            "zip": "00001",
            "email": "medical@pfotenregister.com",
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


def test_medical_event_create_with_attachment_assignment(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    _create_animal(client, guest_id, "Mila")

    with app.app_context():
        animal = Animal.query.filter_by(guest_id=guest_id).order_by(Animal.id.desc()).first()
        assert animal is not None
        attachment = Attachment(
            owner_id=guest_id,
            filename="befund.pdf",
            gcs_path="guest/test/befund.pdf",
            uploaded_on=date.today(),
        )
        db.session.add(attachment)
        db.session.commit()
        animal_id = animal.id
        attachment_id = attachment.id

    response = client.post(
        f"/medical/guest/{guest_id}/create",
        data={
            "animal_id": str(animal_id),
            "title": "Operation Kreuzband",
            "event_type": "Operation",
            "status": "Geplant",
            "priority": "Hoch",
            "planned_for": "2026-04-01",
            "estimated_cost": "1250,50",
            "attachment_ids": [str(attachment_id)],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Medizinischer Vorgang gespeichert".encode("utf-8") in response.data

    with app.app_context():
        event = MedicalEvent.query.filter_by(guest_id=guest_id, title="Operation Kreuzband").first()
        assert event is not None
        assert event.animal_id == animal_id
        assert len(event.attachment_links) == 1
        assert event.attachment_links[0].attachment_id == attachment_id


def test_medical_event_is_visible_on_guest_page(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    _create_animal(client, guest_id, "Loki")

    with app.app_context():
        animal = Animal.query.filter_by(guest_id=guest_id).order_by(Animal.id.desc()).first()
        assert animal is not None
        event = MedicalEvent(
            guest_id=guest_id,
            animal_id=animal.id,
            title="Wundkontrolle",
            event_type="Behandlung",
            status="Aktiv",
            priority="Mittel",
            started_on=date.today(),
        )
        db.session.add(event)
        db.session.commit()

    response = client.get(f"/guest/{guest_id}", follow_redirects=True)
    assert response.status_code == 200
    assert "Gesundheit".encode("utf-8") in response.data
    assert "Wundkontrolle".encode("utf-8") in response.data


def test_attachment_delete_is_blocked_when_linked_to_medical_event(client, app, monkeypatch):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)
    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)

    _create_animal(client, guest_id, "Balu")

    with app.app_context():
        animal = Animal.query.filter_by(guest_id=guest_id).order_by(Animal.id.desc()).first()
        assert animal is not None
        attachment = Attachment(
            owner_id=guest_id,
            filename="rechnung.pdf",
            gcs_path="guest/test/rechnung.pdf",
            uploaded_on=date.today(),
        )
        db.session.add(attachment)
        db.session.flush()
        event = MedicalEvent(
            guest_id=guest_id,
            animal_id=animal.id,
            title="Zahn OP",
            event_type="Operation",
            status="Abgeschlossen",
            priority="Mittel",
            completed_on=date.today(),
        )
        db.session.add(event)
        db.session.flush()
        db.session.add(MedicalEventAttachment(medical_event_id=event.id, attachment_id=attachment.id))
        db.session.commit()
        attachment_id = attachment.id

    delete_calls = []

    def _fake_delete_blob(path: str) -> None:
        delete_calls.append(path)

    monkeypatch.setattr("app.routes.attachement_routes.delete_blob", _fake_delete_blob)

    response = client.post(
        f"/attachment/{attachment_id}/delete",
        headers={"Referer": f"/guest/{guest_id}"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "medizinischen Vorgang".encode("utf-8") in response.data
    assert delete_calls == []

    with app.app_context():
        assert Attachment.query.get(attachment_id) is not None
