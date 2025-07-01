from app.models import Guest, Animal

def test_admin_dashboard_access(client, login):
    """Testet das Laden des Admin-Dashboards."""
    login()

    response = client.get("/admin/")
    assert response.status_code == 200
    assert "Dashboard".encode("utf-8") in response.data
    assert "Gäste insgesamt".encode("utf-8") in response.data


def test_admin_dashboard_data(client, login):
    """Stellt sicher, dass die Dashboarddaten aus der DB geladen werden können."""
    login()

    total_guests = Guest.query.count()
    total_animals = Animal.query.count()

    response = client.get("/admin/")
    assert response.status_code == 200
    assert f"{total_guests}".encode("utf-8") in response.data
    assert f"{total_animals}".encode("utf-8") in response.data