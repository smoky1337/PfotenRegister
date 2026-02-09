from datetime import datetime, date

from app.models import db, Guest


def test_guest_lookup_by_guest_number_redirects(client, login, app):
    login()
    with app.app_context():
        guest = Guest(
            id="AbC123",
            number="G-42",
            firstname="Lookup",
            lastname="Test",
            address="Somewhere 1",
            member_since=date.today(),
            status=True,
            created_on=datetime.now(),
            updated_on=datetime.now(),
        )
        db.session.add(guest)
        db.session.commit()

    response = client.get("/guest/lookup?guest_number=G-42", follow_redirects=False)
    assert response.status_code == 302
    assert "/guest/AbC123" in response.headers["Location"]


def test_guest_lookup_code_is_case_sensitive(client, login, app):
    login()
    with app.app_context():
        guest = Guest(
            id="AbC124",
            number="G-43",
            firstname="Lookup",
            lastname="Case",
            address="Somewhere 2",
            member_since=date.today(),
            status=True,
            created_on=datetime.now(),
            updated_on=datetime.now(),
        )
        db.session.add(guest)
        db.session.commit()

    response = client.get("/guest/lookup?code=abc124", follow_redirects=True)
    assert response.status_code == 200
    assert "Gast-Code nicht gefunden".encode("utf-8") in response.data
