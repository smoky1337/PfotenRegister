import pytest

def test_login_success(client, login):
    """Testet erfolgreichen Login."""
    response = login()
    assert response.status_code == 200
    assert "Barcode".encode("utf-8") in response.data

def test_login_fail(client):
    """Testet fehlerhaften Login."""
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'falsch'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Ungültiger".encode("utf-8") in response.data

def test_logout(client,login):
    """Testet Logout."""
    login()
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert "Anmelden".encode("utf-8") in response.data