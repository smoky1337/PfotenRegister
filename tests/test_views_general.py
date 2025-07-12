import pytest

from app.models import Guest


def test_start(client,login):
    """Testet, ob die Startseite erreichbar ist."""
    login()
    response = client.get('/')
    assert response.status_code == 200
    assert "Barcode".encode("utf-8") in response.data or "Gast".encode("utf-8") in response.data

def test_list_guets(client,login):
    """Testet, ob die Gästeliste-Seite funktioniert."""
    login()

    response = client.get('/guest/list')
    assert response.status_code == 200
    assert "Gästeliste".encode("utf-8") in response.data

def test_view_guest(client,login):
    """Testet die Detailansicht eines Gasts."""
    login()
    guest_ids = [g.id for g in Guest.query.order_by(Guest.created_on.desc()).limit(2).all()]
    guest_ids.append("nichtvorhanden")
    for guest_id in guest_ids:
        response = client.get(f'/guest/{guest_id}', follow_redirects=True)
        if guest_id == "nichtvorhanden":
            assert "Gast nicht gefunden".encode("utf-8") in response.data or response.status_code == 200
        else:
            print(response.data)
            assert response.status_code == 200
            assert "Zahlung".encode("utf-8") in response.data