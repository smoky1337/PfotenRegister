import io
from datetime import date

import flask_login
from app import reports
from app.models import Setting, db


class _Record:
    def __init__(self):
        self.paid_on = date.today()
        self.number = "G-1"
        self.firstname = "Max"
        self.lastname = "Muster"
        self.food_amount = 5.0
        self.other_amount = 2.0
        self.comment = "Test"


def test_generate_payment_report_returns_pdf(app, monkeypatch):
    with app.app_context():
        setting = Setting.query.filter_by(setting_key="logourl").first()
        if setting:
            setting.value = ""
            db.session.commit()

    class _User:
        realname = "Tester"

    monkeypatch.setattr(flask_login, "current_user", _User())

    with app.app_context():
        buffer = reports.generate_payment_report([_Record()], date.today(), date.today())
        assert isinstance(buffer, io.BytesIO)
        assert buffer.getbuffer().nbytes > 0


def test_generate_multiple_gast_cards_pdf_dispatch(app, monkeypatch):
    with app.app_context():
        setting = Setting.query.filter_by(setting_key="guestCardFormat").first()
        if setting:
            setting.value = "LP898"
            db.session.commit()

    def _fake_lp(*_args, **_kwargs):
        return io.BytesIO(b"lp")

    def _fake_dp(*_args, **_kwargs):
        return io.BytesIO(b"dp")

    monkeypatch.setattr(reports, "generate_multiple_gast_cards_pdf_LP898", _fake_lp)
    monkeypatch.setattr(reports, "generate_multiple_gast_cards_pdf_DP839", _fake_dp)

    with app.app_context():
        result = reports.generate_multiple_gast_cards_pdf(["X"], double_sided=False)
        assert isinstance(result, io.BytesIO)
        assert result.read() == b"lp"
