import os
import sys
from pathlib import Path
from typing import Generator

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from sqlalchemy import Date, DateTime

from app.models import db, FieldRegistry, Setting


def _set_test_env_defaults() -> None:
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_DATABASE", "pfotenregister_test")
    os.environ.setdefault("DB_PORT", "3306")
    os.environ.setdefault("DB_USER", "test")
    os.environ.setdefault("DB_PASSWORD", "test")
    os.environ.setdefault("GCS_BUCKET_NAME", "pfotenregister-test")


@pytest.fixture(scope="session")
def app() -> Generator:
    _set_test_env_defaults()
    app = create_app(
        {
            "TESTING": True,
            "SETTINGS": {
                "primarycolour": {"value": "#0d6efd", "description": "Primary Color"},
                "logourl": {"value": "", "description": "Logo URL"},
                "name": {"value": "TESTBED", "description": "Testbed"},
                "primaryColor": {"value": "#0d6efd", "description": "Primary Color"},
            },
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clean_db(app):
    with app.app_context():
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
    yield
    with app.app_context():
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture(autouse=True)
def _seed_settings(app):
    with app.app_context():
        defaults = [
            ("name", "Pfotenregister (DEV)", "Name"),
            ("primarycolour", "#1b4750", "Primary Color"),
            ("primaryColor", "#1b4750", "Primary Color"),
            ("logourl", "", "Logo URL"),
            ("maxAnimals", "3", "Max Animals"),
            ("minTimeFood", "14", "Min Time Food"),
            ("adminEmail", "admin@pfotenregister.com", "Admin Email"),
            ("payments", "Aktiv", "Zahlungen"),
            ("tagsystem", "Aktiv", "Tagsystem"),
            ("guestNumberFormat", "YYYYNNN", "Guest Number Format"),
            ("guestCardFormat", "LP898", "Guest Card Format"),
            ("locations", "Aktiv", "Standorte"),
            ("guestCardEmailSubject", "Deine digitale Gästekarte der Tiertafel Osnabrück", "Guest Card Email Subject"),
            ("guestCardEmailReplyTo", "louis.scheu@t-online.de", "Guest Card Email Reply-To"),
            (
                "guestCardEmailBody",
                "Hallo {{first_name}} {{last_name}},\n"
                "hier ist deine digitale Gästekarte für die Tiertafel Osnabrück.\n"
                "Bitte bringe diese digital bei Ausgaben mit. Dein Code ist {{guest_id}}.\n"
                "Liebe Grüße,\n"
                "Dein Team der Tiertafel Osnabrück\n"
                "(Gesendet von Pfotenregister)",
                "Guest Card Email Body",
            ),
            ("locationGuestAssigment", "Aktiv", "Standorte-Gast-Zuordnung"),
            ("foodplans", "Aktiv", "Futterpläne"),
        ]
        for key, value, desc in defaults:
            if not Setting.query.filter_by(setting_key=key).first():
                db.session.add(
                    Setting(setting_key=key, value=value, description=desc)
                )
        db.session.commit()
        if hasattr(app, "refresh_settings"):
            app.refresh_settings()
    yield


@pytest.fixture(autouse=True)
def _seed_field_registry(app):
    with app.app_context():
        models = [mapper.class_ for mapper in db.Model.registry.mappers]
        for model in models:
            if not hasattr(model, "__tablename__"):
                continue
            model_name = model.__name__
            if model_name not in ("Guest", "Animal", "Representative"):
                continue
            for column in model.__table__.columns:
                field_name = column.name
                exists = FieldRegistry.query.filter_by(
                    model_name=model_name,
                    field_name=field_name,
                ).first()
                if exists:
                    continue
                is_optional = column.nullable or column.default is not None or column.server_default is not None
                is_remindable = isinstance(column.type, (Date, DateTime))
                db.session.add(
                    FieldRegistry(
                        model_name=model_name,
                        field_name=field_name,
                        globally_visible=True,
                        optional=is_optional,
                        visibility_level="User",
                        editability_level="Editor",
                        ui_label=field_name.replace("_", " ").capitalize(),
                        show_inline=True,
                        display_order=0,
                        remindable=is_remindable,
                    )
                )
        db.session.commit()
    yield
