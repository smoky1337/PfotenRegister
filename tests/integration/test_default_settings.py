from app.default_settings import DEFAULT_SETTINGS, ensure_default_settings
from app.models import Setting, db


def test_default_settings_are_inserted_without_overwriting_existing_values(app):
    with app.app_context():
        db.session.query(Setting).delete()
        db.session.add(
            Setting(
                setting_key="name",
                value="Meine Tiertafel",
                description="Eigener Name",
            )
        )
        db.session.commit()

        inserted_count = ensure_default_settings()
        app.refresh_settings()

        assert inserted_count == len(DEFAULT_SETTINGS) - 1
        assert Setting.query.count() == len(DEFAULT_SETTINGS)
        assert app.config["SETTINGS"]["name"]["value"] == "Meine Tiertafel"

        assert ensure_default_settings() == 0


def test_login_page_renders_with_empty_settings_context(client, app, monkeypatch):
    with app.app_context():
        monkeypatch.setitem(app.config, "SETTINGS", {})

    response = client.get("/login")

    assert response.status_code == 200
    assert b"PfotenRegister" in response.data
