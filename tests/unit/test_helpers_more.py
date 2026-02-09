from datetime import date, datetime, timedelta

import pytest

from app import helpers
from app.models import FieldRegistry, Guest, db


def test_generate_guest_number_uses_format(app, monkeypatch):
    class _Setting:
        value = "YYMM-NNN"

    class _Query:
        def filter_by(self, **_kwargs):
            return self

        def first(self):
            return _Setting()

    class _GuestQuery:
        def with_entities(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            return []

    import app.models as models

    monkeypatch.setattr(models.Setting, "query", _Query())
    monkeypatch.setattr(models.Guest, "query", _GuestQuery())

    number = helpers.generate_guest_number()
    assert number.endswith("001")


def test_build_reminder_alerts_guest_missing_date(app):
    with app.app_context():
        field = FieldRegistry.query.filter_by(model_name="Guest", field_name="birthdate").first()
        assert field is not None
        field.remindable = True
        field.reminder_interval_days = 10
        db.session.commit()

        guest = Guest(
            id="X",
            number="N1",
            firstname="Max",
            lastname="Muster",
            address="A",
            member_since=date.today(),
            status=True,
            created_on=date.today(),
            updated_on=date.today(),
        )
        alerts = helpers.build_reminder_alerts(guest)
        assert any(a["status"] == "missing" for a in alerts)


def test_build_reminder_alerts_guest_overdue(app):
    with app.app_context():
        field = FieldRegistry.query.filter_by(model_name="Guest", field_name="birthdate").first()
        assert field is not None
        field.remindable = True
        field.reminder_interval_days = 1
        db.session.commit()

        guest = Guest(
            id="X",
            number="N1",
            firstname="Max",
            lastname="Muster",
            address="A",
            birthdate=date.today() - timedelta(days=10),
            member_since=date.today(),
            status=True,
            created_on=date.today(),
            updated_on=date.today(),
        )
        alerts = helpers.build_reminder_alerts(guest)
        assert any(a["status"] == "overdue" for a in alerts)
