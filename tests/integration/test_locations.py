import uuid

from werkzeug.security import generate_password_hash

from app.models import DropOffLocation, User, db


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


def _create_location_payload():
    return {
        "name": "Ausgabestelle A",
        "address": "Musterstr. 1",
        "city": "Osnabrueck",
        "latitude": 52.2799,
        "longitude": 8.0472,
        "location_type": "dispense",
        "is_dispense_location": True,
        "responsible_person": "Max Mustermann",
        "comments": "Test Standort",
        "active": True,
    }


def test_locations_map_view(client, app):
    _bootstrap_login(client, app)
    response = client.get("/locations/", follow_redirects=True)
    assert response.status_code == 200
    assert "Standorte".encode("utf-8") in response.data
    assert "Einbettungscode exportieren".encode("utf-8") in response.data


def test_locations_create_and_list(client, app):
    _bootstrap_login(client, app)
    response = client.post("/locations/api", json=_create_location_payload())
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["name"] == "Ausgabestelle A"

    response = client.get("/locations/api")
    assert response.status_code == 200
    data = response.get_json()
    assert any(item["name"] == "Ausgabestelle A" for item in data)


def test_locations_update(client, app):
    _bootstrap_login(client, app)
    response = client.post("/locations/api", json=_create_location_payload())
    location_id = response.get_json()["id"]

    response = client.patch(
        f"/locations/api/{location_id}",
        json={"name": "Ausgabestelle B", "last_emptied": "2026-02-01"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["name"] == "Ausgabestelle B"
    assert payload["last_emptied"] == "2026-02-01"


def test_locations_empty(client, app):
    _bootstrap_login(client, app)
    response = client.post("/locations/api", json=_create_location_payload())
    location_id = response.get_json()["id"]

    response = client.post(f"/locations/api/{location_id}/empty")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["last_emptied"] is not None


def test_locations_delete(client, app):
    _bootstrap_login(client, app)
    response = client.post("/locations/api", json=_create_location_payload())
    location_id = response.get_json()["id"]

    response = client.delete(f"/locations/api/{location_id}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["deleted"] is True

    with app.app_context():
        assert DropOffLocation.query.get(location_id) is None


def test_location_embed_code_contains_only_selected_public_data(client, app):
    _bootstrap_login(client, app)
    selected_payload = _create_location_payload()
    selected_payload.update({
        "name": "</script><script>alert('x')</script>",
        "responsible_person": "Interne Person",
        "comments": "Interne Notiz",
    })
    selected_response = client.post("/locations/api", json=selected_payload)
    other_payload = _create_location_payload()
    other_payload["name"] = "Nicht exportieren"
    client.post("/locations/api", json=other_payload)

    response = client.post(
        "/locations/embed-code",
        json={"location_ids": [selected_response.get_json()["id"]]},
    )

    assert response.status_code == 200
    payload = response.get_json()
    code = payload["code"]
    assert payload["location_count"] == 1
    assert "Musterstr. 1" in code
    assert "\\u003c/script\\u003e" in code
    assert "</script><script>alert" not in code
    assert "Nicht exportieren" not in code
    assert "Interne Person" not in code
    assert "Interne Notiz" not in code
    assert "https://tile.openstreetmap.org/{z}/{x}/{y}.png" in code
    assert "OpenStreetMap" in code
    assert "nominatim" not in code.lower()
    assert 'window.location.protocol === "file:"' in code
    assert "python -m http.server 8000" in code


def test_location_embed_code_rejects_empty_or_inactive_selection(client, app):
    _bootstrap_login(client, app)
    empty_response = client.post("/locations/embed-code", json={"location_ids": []})
    assert empty_response.status_code == 400

    inactive_payload = _create_location_payload()
    inactive_payload["active"] = False
    inactive_response = client.post("/locations/api", json=inactive_payload)
    response = client.post(
        "/locations/embed-code",
        json={"location_ids": [inactive_response.get_json()["id"]]},
    )
    assert response.status_code == 400
