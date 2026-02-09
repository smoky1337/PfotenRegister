import io
import os
import uuid
from datetime import date

import pandas as pd
from werkzeug.security import generate_password_hash

from app.models import Guest, User, db


def _create_user(username: str, password: str, role: str = "admin") -> None:
    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
        realname=username,
    )
    db.session.add(user)
    db.session.commit()


def _login(client, username: str, password: str) -> None:
    response = client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
    assert response.status_code == 200


def _bootstrap_login(client, app) -> None:
    username = f"admin-{uuid.uuid4().hex[:8]}"
    password = "admin"
    with app.app_context():
        _create_user(username, password)
    _login(client, username, password)


def _write_import_file(tmp_path: str) -> str:
    os.makedirs(tmp_path, exist_ok=True)
    filepath = os.path.join(tmp_path, "test_import.xlsx")

    guests = pd.DataFrame(
        [
            {
                "nummer": "G-100",
                "vorname": "Max",
                "nachname": "Muster",
                "adresse": "Testweg 1",
                "ort": "Teststadt",
                "plz": "12345",
                "status": "1",
            }
        ]
    )
    animals = pd.DataFrame(
        [
            {
                "gast_nummer": "G-100",
                "art": "Hund",
                "name": "Fifi",
                "geschlecht": "m",
                "active": "1",
            }
        ]
    )

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        guests.to_excel(writer, sheet_name="gaeste", index=False)
        animals.to_excel(writer, sheet_name="tiere", index=False)

    return filepath


def test_admin_import_get(client, app):
    _bootstrap_login(client, app)
    response = client.get("/admin/import", follow_redirects=True)
    assert response.status_code == 200
    assert "Datenimport".encode("utf-8") in response.data


def test_admin_import_invalid_file(client, app):
    _bootstrap_login(client, app)
    data = {"file": (io.BytesIO(b"bad"), "bad.txt")}
    response = client.post(
        "/admin/import",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "gültige .xlsx Datei".encode("utf-8") in response.data


def test_admin_import_upload_redirects_to_preview(client, app, tmp_path):
    _bootstrap_login(client, app)
    filepath = _write_import_file(str(tmp_path))
    with open(filepath, "rb") as fh:
        data = {"file": (fh, "test_import.xlsx")}
        response = client.post(
            "/admin/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
    assert response.status_code == 302
    assert "/admin/import/preview" in response.headers.get("Location", "")


def test_admin_import_preview(client, app, tmp_path):
    _bootstrap_login(client, app)
    filepath = _write_import_file("tmp")
    filename = os.path.basename(filepath)

    response = client.get(
        f"/admin/import/preview?filepath={filename}",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Importvorschau".encode("utf-8") in response.data


def test_admin_import_confirm(client, app, tmp_path):
    _bootstrap_login(client, app)
    filepath = _write_import_file("tmp")
    filename = os.path.basename(filepath)

    response = client.get(
        f"/admin/import/confirm?filepath={filename}",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Import erfolgreich".encode("utf-8") in response.data


def test_admin_export_get(client, app):
    _bootstrap_login(client, app)
    response = client.get("/admin/export", follow_redirects=True)
    assert response.status_code == 200
    assert "Daten exportieren".encode("utf-8") in response.data


def test_admin_export_post_no_selection(client, app):
    _bootstrap_login(client, app)
    response = client.post(
        "/admin/export",
        data={},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "mindestens eine Spalte".encode("utf-8") in response.data


def test_admin_export_post_with_selection(client, app):
    _bootstrap_login(client, app)
    with app.app_context():
        guest = Guest(
            id="G1",
            number="G-1",
            firstname="Max",
            lastname="Muster",
            address="Testweg 1",
            member_since=date.today(),
            status=True,
            created_on=date.today(),
            updated_on=date.today(),
        )
        db.session.add(guest)
        db.session.commit()

    response = client.post(
        "/admin/export",
        data={
            "fields[guests][]": ["firstname", "lastname", "number"],
            "include_header": "on",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
