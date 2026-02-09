from datetime import datetime
from app.models import Guest
from datetime import datetime

from app.models import Guest


def test_register_animal_minimal(client,login):
    """Registriert ein Tier mit minimalen Pflichtfeldern."""
    guest_id = Guest.query.order_by(Guest.created_on.desc()).offset(1).first().id
    login()


    # Minimaler Tier-Eintrag
    response = client.post("/animals/register", data={
        "guest_id": guest_id,
        "species": "Hund",
        "name": "Fifi",
        "castrated": "Ja",
        "food_type": "Trocken",
        "complete_care": "Unbekannt",
        "status": "1"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Fifi".encode("utf-8") in response.data


def test_register_animal_maximal(client,login):
    """Registriert ein Tier mit allen möglichen Feldern."""
    heute = datetime.today().strftime('%Y-%m-%d')
    login()
    guest_id = Guest.query.order_by(Guest.created_on.desc()).first().id
    # Maximaler Tier-Eintrag
    response = client.post("/animals/register", data={
        "guest_id": guest_id,
        "species": "Katze",
        "race": "Perser",
        "name": "Miezi",
        "sex": "F",
        "color": "Weiß",
        "castrated": "Ja",
        "identification": "CHIP-12345",
        "birthdate": "2015-04-04",
        "weight_or_size": "4kg",
        "illnesses": "Asthma",
        "allergies": "Fisch",
        "food_type": "Misch",
        "complete_care": "Ja",
        "last_seen": heute,
        "veterinarian": "Dr. Katz",
        "food_amount_note": "2kg Nassfutter",
        "tax_until": "2025-12-31",
        "status": "1",
        "note": "Braucht ruhigen Platz",
        "pet_registry": "TassoX3412",
        "died_on": heute,
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Miezi".encode("utf-8") in response.data