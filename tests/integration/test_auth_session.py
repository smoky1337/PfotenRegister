import uuid

from werkzeug.security import generate_password_hash

from app.models import User, db


def _create_user(username: str, password: str, role: str = "admin") -> User:
    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
        realname=username,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_login_success(client, app):
    with app.app_context():
        _create_user(f"admin-{uuid.uuid4().hex[:8]}", "admin")

    response = client.post(
        "/login",
        data={"username": User.query.order_by(User.id.desc()).first().username, "password": "admin"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Erfolgreich angemeldet".encode("utf-8") in response.data


def test_login_failure(client, app):
    with app.app_context():
        _create_user(f"admin-{uuid.uuid4().hex[:8]}", "admin")

    response = client.post(
        "/login",
        data={"username": User.query.order_by(User.id.desc()).first().username, "password": "wrong"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Ungültiger Benutzername oder Passwort".encode("utf-8") in response.data


def test_logout_requires_login(client):
    response = client.get("/logout", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")


def test_logout_clears_session(client, app):
    with app.app_context():
        _create_user(f"admin-{uuid.uuid4().hex[:8]}", "admin")

    client.post(
        "/login",
        data={"username": User.query.order_by(User.id.desc()).first().username, "password": "admin"},
        follow_redirects=True,
    )

    response = client.get("/logout", follow_redirects=True)

    assert response.status_code == 200
    assert "Erfolgreich abgemeldet".encode("utf-8") in response.data


def test_protected_route_redirects_to_login(client):
    response = client.get("/guest/list", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")
