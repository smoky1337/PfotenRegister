import io
from datetime import date

from app import reports
from app.models import Setting, db


class _Record:
    def __init__(self, idx):
        self.paid_on = date.today()
        self.number = f"G-{idx}"
        self.firstname = "Max"
        self.lastname = "Muster"
        self.food_amount = 1.0
        self.other_amount = 1.0
        self.comment = "Test"


def test_generate_payment_report_multiple_pages(app, monkeypatch):
    with app.app_context():
        setting = Setting.query.filter_by(setting_key="logourl").first()
        if setting:
            setting.value = ""
            db.session.commit()

    class _User:
        realname = "Tester"

    import flask_login

    monkeypatch.setattr(flask_login, "current_user", _User())

    records = [_Record(i) for i in range(30)]
    with app.app_context():
        buffer = reports.generate_payment_report(records, date.today(), date.today())
        assert isinstance(buffer, io.BytesIO)
        assert buffer.getbuffer().nbytes > 0


def test_generate_multiple_gast_cards_pdf_dp839(app, monkeypatch):
    with app.app_context():
        setting = Setting.query.filter_by(setting_key="guestCardFormat").first()
        if setting:
            setting.value = "DP839"
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
        assert result.read() == b"dp"
