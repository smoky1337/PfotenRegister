from datetime import datetime

from app.helpers import (
    _build_guest_card_email_html,
    _render_guest_card_template,
    _settings_value,
    format_date,
    format_date_iso,
    is_active,
    is_different,
)
from app.models import Guest


def test_format_date_from_datetime():
    dt = datetime(2025, 1, 2)
    assert format_date(dt) == "02-01-2025"


def test_format_date_from_string():
    assert format_date("2025-01-02") == "02-01-2025"


def test_format_date_iso_from_datetime():
    dt = datetime(2025, 1, 2)
    assert format_date_iso(dt) == "2025-01-02"


def test_format_date_iso_from_string():
    assert format_date_iso("02-01-2025") == "2025-01-02"


def test_is_different_handles_none_and_empty():
    assert is_different(None, "") is False
    assert is_different("", None) is False
    assert is_different("1", 1) is False
    assert is_different("2", 1) is True


def test_render_guest_card_template():
    guest = Guest(id="ABCD", number="N-1", firstname="Max", lastname="Muster")
    tpl = "{{first_name}} {{last_name}} {{guest_id}} {{guest_number}}"
    rendered = _render_guest_card_template(tpl, guest)
    assert rendered == "Max Muster ABCD N-1"


def test_settings_value_from_dict():
    settings = {"name": {"value": "Pfoten"}}
    assert _settings_value(settings, "name") == "Pfoten"


def test_build_guest_card_email_html_contains_guest_data():
    guest = Guest(id="ABCD", number="N-1", firstname="Max", lastname="Muster")
    html = _build_guest_card_email_html({}, guest, "Hallo")
    assert "Gast-ID" in html
    assert "ABCD" in html
    assert "N-1" in html


def test_is_active_true_when_setting_active():
    class _FakeApp:
        config = {"SETTINGS": {"payments": {"value": "Aktiv"}}}

    assert is_active("payments", app=_FakeApp()) is True


def test_is_active_false_when_setting_inactive():
    class _FakeApp:
        config = {"SETTINGS": {"payments": {"value": "Inaktiv"}}}

    assert is_active("payments", app=_FakeApp()) is False
