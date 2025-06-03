from datetime import datetime
from app import db_cursor


def _create_procedure(client, login):
    login()
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM gaeste ORDER BY erstellt_am DESC LIMIT 1")
        guest_id = cursor.fetchone()["id"]
        cursor.execute("SELECT id FROM tiere WHERE gast_id = %s ORDER BY erstellt_am DESC LIMIT 1", (guest_id,))
        animal_id = cursor.fetchone()["id"]

    today = datetime.today().strftime("%Y-%m-%d")
    response = client.post(f"/guest/{guest_id}/{animal_id}/procedures/new", data={
        "datum": today,
        "beschreibung": "Testbehandlung",
        "kosten": "15.00",
        "anzahl_vorauszahlung": "5.00",
        "grund": "Test"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Behandlung hinzugef" in response.data

    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM tierbehandlungen ORDER BY id DESC LIMIT 1")
        proc_id = cursor.fetchone()["id"]

    return guest_id, animal_id, proc_id


def test_create_procedure(client, login):
    guest_id, animal_id, proc_id = _create_procedure(client, login)
    assert proc_id is not None


def test_edit_procedure(client, login):
    ids = _create_procedure(client, login)
    guest_id, animal_id, proc_id = ids
    today = datetime.today().strftime("%Y-%m-%d")
    response = client.post(f"/guest/{guest_id}/{animal_id}/procedures/{proc_id}/edit", data={
        "datum": today,
        "beschreibung": "Geaendert",
        "kosten": "20.00",
        "anzahl_vorauszahlung": "10.00",
        "grund": "Update"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Behandlung aktualisiert" in response.data


def test_delete_procedure(client, login):
    ids = _create_procedure(client, login)
    guest_id, animal_id, proc_id = ids
    response = client.post(f"/guest/{guest_id}/{animal_id}/procedures/{proc_id}/delete", follow_redirects=True)
    assert response.status_code == 200
    assert b"Behandlung gel" in response.data

