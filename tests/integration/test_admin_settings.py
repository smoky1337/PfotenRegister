import uuid

from werkzeug.security import generate_password_hash

from app.models import FieldRegistry, Setting, User, db


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


def test_admin_settings_update(client, app):
    _bootstrap_login(client, app)
    response = client.post(
        "/admin/settings",
        data={"name": "PfotenRegister Test"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Einstellungen wurden gespeichert".encode("utf-8") in response.data

    with app.app_context():
        setting = Setting.query.filter_by(setting_key="name").first()
        assert setting is not None
        assert setting.value == "PfotenRegister Test"


def test_admin_field_visibility_update(client, app):
    _bootstrap_login(client, app)
    with app.app_context():
        field = FieldRegistry.query.first()
        assert field is not None
        field_id = field.id

    with app.app_context():
        fields = FieldRegistry.query.all()
        form_data = {
            "visible_fields": [str(field_id)],
        }
        for f in fields:
            form_data[f"visibility_level_{f.id}"] = f.visibility_level or "Admin"
            form_data[f"editability_level_{f.id}"] = f.editability_level or "Editor"
            form_data[f"ui_label_{f.id}"] = f.ui_label or f.field_name.replace("_", " ").capitalize()
            form_data[f"display_order_{f.id}"] = str(f.display_order or 0)
            if f.show_inline:
                form_data[f"show_inline_{f.id}"] = "on"

    response = client.post(
        "/admin/field_visibility",
        data=form_data,
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Feldsichtbarkeit wurde aktualisiert".encode("utf-8") in response.data


def test_admin_reminder_settings_update(client, app):
    _bootstrap_login(client, app)
    with app.app_context():
        field = (
            FieldRegistry.query.filter(FieldRegistry.model_name == "Guest")
            .filter(FieldRegistry.field_name.in_(["birthdate", "member_since", "member_until"]))
            .first()
        )
        assert field is not None
        field_id = field.id

    response = client.post(
        "/admin/reminders",
        data={
            f"remindable_{field_id}": "on",
            f"reminder_interval_{field_id}": "30",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Erinnerungseinstellungen gespeichert".encode("utf-8") in response.data
