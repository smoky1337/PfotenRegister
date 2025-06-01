import pytest

from app import db_cursor


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
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM gaeste ORDER BY erstellt_am DESC LIMIT 2")
        guest_ids = [row["id"] for row in cursor.fetchall()]
    guest_ids.append("nichtvorhanden")
    for guest_id in guest_ids:
        response = client.get(f'/guest/{guest_id}', follow_redirects=True)
        if guest_id == "nichtvorhanden":
            assert "Gast nicht gefunden".encode("utf-8") in response.data or response.status_code == 200
        else:
            print(response.data)
            assert response.status_code == 200
            assert "Gastdetails".encode("utf-8") in response.data