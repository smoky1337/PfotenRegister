import uuid

from werkzeug.security import generate_password_hash

from app.models import FoodPlan, FoodPlanGuest, Guest, User, db


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
    unique_lastname = f"Plan-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/guest/register",
        data={
            "firstname": "Plan",
            "lastname": unique_lastname,
            "address": "Planweg 1",
            "city": "Kurzdorf",
            "zip": "00001",
            "email": "plan@pfotenregister.com",
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


def _create_plan(client) -> int:
    response = client.post(
        "/food-plans/new",
        data={
            "title": "Plan A",
            "mode": "guest_view",
            "status": "Planen",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/food-plans/" in response.headers.get("Location", "")

    plan = FoodPlan.query.order_by(FoodPlan.id.desc()).first()
    assert plan is not None
    return plan.id


def test_food_plan_list(client, app):
    _bootstrap_login(client, app)
    response = client.get("/food-plans/", follow_redirects=True)
    assert response.status_code == 200
    assert "Futterpl".encode("utf-8") in response.data


def test_food_plan_create_and_edit(client, app):
    _bootstrap_login(client, app)
    with app.app_context():
        plan_id = _create_plan(client)

    response = client.post(
        f"/food-plans/{plan_id}/edit",
        data={
            "title": "Plan B",
            "mode": "type_view",
            "status": "Packen",
            "location_id": "",
            "general_note": "Testnotiz",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Futterplan gespeichert".encode("utf-8") in response.data


def test_food_plan_add_guest_and_note(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)

    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        plan_id = _create_plan(client)

    response = client.post(
        f"/food-plans/{plan_id}/guests/add",
        data={"guest_id": guest_id, "recent_food_filter": "all"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Gast hinzugefügt".encode("utf-8") in response.data

    response = client.post(
        f"/food-plans/{plan_id}/guests/{guest_id}/note",
        data={"note": "Bitte Nassfutter"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Notiz gespeichert".encode("utf-8") in response.data


def test_food_plan_bulk_add_and_clear(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)

    with app.app_context():
        _get_guest_id(unique_lastname)
        plan_id = _create_plan(client)

    response = client.post(
        f"/food-plans/{plan_id}/guests/bulk_add",
        data={"action": "all_guests", "recent_food_filter": "all"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    response = client.post(
        f"/food-plans/{plan_id}/guests/clear",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Gäste entfernt".encode("utf-8") in response.data


def test_food_plan_preview_and_print(client, app):
    _bootstrap_login(client, app)
    with app.app_context():
        plan_id = _create_plan(client)

    response = client.get(f"/food-plans/{plan_id}/preview", follow_redirects=True)
    assert response.status_code == 200

    response = client.get(f"/food-plans/{plan_id}/print", follow_redirects=True)
    assert response.status_code == 200


def test_food_plan_remove_guest_and_delete(client, app):
    _bootstrap_login(client, app)
    unique_lastname = _create_guest(client)

    with app.app_context():
        guest_id = _get_guest_id(unique_lastname)
        plan_id = _create_plan(client)
        db.session.add(FoodPlanGuest(food_plan_id=plan_id, guest_id=guest_id, sort_order=1))
        db.session.commit()

    response = client.post(
        f"/food-plans/{plan_id}/guests/{guest_id}/remove",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Gast entfernt".encode("utf-8") in response.data

    response = client.post(
        f"/food-plans/{plan_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Futterplan gelöscht".encode("utf-8") in response.data

    with app.app_context():
        assert FoodPlan.query.get(plan_id) is None
