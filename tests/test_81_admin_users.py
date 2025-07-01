from app.models import User


def test_list_users(client, login):
    """Testet die Übersicht der Benutzerverwaltung."""
    login()
    response = client.get("/admin/list_users")
    assert response.status_code == 200
    assert "Benutzerverwaltung".encode("utf-8") in response.data


def test_create_user(client, login):
    """Testet das Erstellen eines neuen Benutzers."""
    login()

    response = client.post("/admin/users/register", data={
        "username": "pytest_user",
        "password": "testpass123",
        "role": "editor",
        "realname": "pytest_user",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Benutzer erfolgreich angelegt".encode("utf-8") in response.data

    # Prüfe ob Benutzer in der DB existiert
    assert User.query.filter_by(username="pytest_user").first() is not None


def test_edit_user(client, login):
    """Testet das Bearbeiten eines bestehenden Benutzers."""
    login()

    user = User.query.filter_by(username="pytest_user").first()
    assert user is not None
    user_id = user.id

    response = client.post(f"/admin/users/{user_id}/edit", data={
        "username": "pytest_user",
        "role": "user",
        "realname": "pytest_nutzer",

    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Benutzer erfolgreich aktualisiert".encode("utf-8") in response.data


def test_delete_user(client, login):
    """Testet das Löschen eines Benutzers."""
    login()

    user = User.query.filter_by(username="pytest_user").first()
    assert user is not None
    user_id = user.id

    response = client.post(f"/admin/users/{user_id}/delete", follow_redirects=True)
    assert response.status_code == 200
    assert "Benutzer erfolgreich gelöscht".encode("utf-8") in response.data

    # Prüfen, ob der Benutzer entfernt wurde
    assert User.query.get(user_id) is None
