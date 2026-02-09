from app.models import Guest, Animal


def test_update_guest(client, login):
    login()

    guest = Guest.query.order_by(Guest.created_on.desc()).first()
    guest_id = guest.id

    response = client.post(f"/guest/{guest_id}/update", data={
        "firstname": guest.firstname,
        "lastname": guest.lastname,
        "number": guest.number,
        "address": "Langweg 23",
        "zip": guest.zip or "",
        "city": guest.city or "",
        "phone": guest.phone or "",
        "mobile": guest.mobile or "",
        "email": guest.email or "",
        "birthdate": guest.birthdate,
        "gender": guest.gender,
        "member_since": guest.member_since,
        "member_until": guest.member_until or "",
        "r_name": guest.representative[0].name if guest.representative else "",
        "r_phone": guest.representative[0].phone if guest.representative else "",
        "r_email": guest.representative[0].email if guest.representative else "",
        "r_address": guest.representative[0].address if guest.representative else "",
        "status": guest.status,
        "indigence": guest.indigence or "",
        "indigent_until": guest.indigent_until.isoformat() if guest.indigent_until else "",
        "documents": guest.documents or "",
        "notes": guest.notes or ""
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Langweg 23".encode("utf-8") in response.data


def test_update_animal(client, login):
    login()
    # Hole ein Tier und seinen zugehörigen Gast
    animal = Animal.query.order_by(Animal.created_on.desc()).first()
    assert animal, "Es wurde kein Tier in der Datenbank gefunden."
    animal_id = animal.id

    response = client.post(f"/animals/{animal_id}/update", data={
        "species": animal.species or "",
        "breed": animal.breed or "",
        "name": "NEUER NAME",
        "sex": animal.sex or "",
        "color": animal.color or "",
        "castrated": animal.castrated or "",
        "identification": animal.identification or "",
        "birthdate": animal.birthdate.isoformat() if animal.birthdate else "",
        "weight_or_size": animal.weight_or_size or "",
        "illnesses": animal.illnesses or "",
        "allergies": animal.allergies or "",
        "food_type": animal.food_type or "",
        "complete_care": animal.complete_care or "",
        "last_seen": animal.last_seen.isoformat() if animal.last_seen else "",
        "veterinarian": animal.veterinarian or "",
        "food_amount_note": animal.food_amount_note or "",
        "note": animal.note or ""
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "NEUER NAME".encode("utf-8") in response.data


def test_edit_guest_notes(client, login):
    """Testet das Aktualisieren der Notizen eines Gastes."""
    login()

    guest_id = Guest.query.order_by(Guest.created_on.desc()).first().id

    new = "Testnotiz für Gast"
    response = client.post(f"/guest/{guest_id}/edit_notes", data={
        "notizen": new
    }, follow_redirects=True)

    assert response.status_code == 200
    assert "Testnotiz" in Guest.query.order_by(Guest.created_on.desc()).first().notes



def test_edit_animal_notes(client, login):
    """Testet das Aktualisieren der Notizen eines Tiers."""
    login()

    guest_id = Guest.query.order_by(Guest.created_on.desc()).first().id

    animal_id = (
        Animal.query.filter_by(guest_id=guest_id)
        .order_by(Animal.created_on.desc())
        .first()
        .id
    )

    new = "Testnotiz für Tier"
    response = client.post(f"/animals/{animal_id}/edit_note", data={
        "notizen": new
    }, follow_redirects=True)

    assert response.status_code == 200
    assert new.encode("utf-8") in response.data
