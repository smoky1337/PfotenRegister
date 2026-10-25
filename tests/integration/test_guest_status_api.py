import hashlib
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.models import Guest, User, db


@pytest.fixture
def api_headers(app, monkeypatch):
    """Configure a disposable token without depending on deployment secrets."""
    token = "test-only-guest-api-token"
    monkeypatch.setitem(
        app.config,
        "GUEST_STATUS_API_TOKEN_SHA256",
        hashlib.sha256(token.encode()).hexdigest(),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    "lifecycle_status,legacy_status,expected_active",
    [("active", False, True), ("inactive", True, False), ("staging", True, False)],
)
def test_guest_status_returns_only_public_flags(
    client, app, api_headers, lifecycle_status, legacy_status, expected_active
):
    with app.app_context():
        db.session.add(Guest(
            id="Guest-Code-123",
            number="2026001",
            firstname="Private",
            lastname="Details",
            email="private@example.org",
            member_since=date.today(),
            created_on=date.today(),
            updated_on=date.today(),
            lifecycle_status=lifecycle_status,
            status=legacy_status,
        ))
        db.session.commit()

    response = client.post(
        "/api/v1/guest-status", json={"code": " Guest-Code-123 "}, headers=api_headers
    )

    assert response.status_code == 200
    assert response.get_json() == {"exists": True, "active": expected_active}
    assert response.headers["Cache-Control"] == "no-store"


def test_unknown_guest_returns_null_active(client, api_headers):
    response = client.post(
        "/api/v1/guest-status", json={"code": "unknown"}, headers=api_headers
    )
    assert response.status_code == 200
    assert response.get_json() == {"exists": False, "active": None}


@pytest.mark.parametrize(
    "authorization", [None, "", "Basic abc", "Bearer", "Bearer wrong", "Bearer a b"]
)
def test_invalid_authentication_precedes_payload_validation(client, api_headers, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}
    response = client.post("/api/v1/guest-status", json={}, headers=headers)
    assert response.status_code == 401
    assert response.is_json
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("configured_hash", ["", "not-a-hash", "x" * 64, None])
def test_unconfigured_api_is_unavailable(client, app, api_headers, monkeypatch, configured_hash):
    monkeypatch.setitem(app.config, "GUEST_STATUS_API_TOKEN_SHA256", configured_hash)
    response = client.post("/api/v1/guest-status", json={"code": "unknown"}, headers=api_headers)
    assert response.status_code == 503
    assert response.is_json


@pytest.mark.parametrize("environment_hash", [None, "", "invalid-hash"])
def test_optional_api_configuration_does_not_affect_normal_app(monkeypatch, environment_hash):
    """Verify startup, health checks and browser login during a partial rollout."""
    if environment_hash is None:
        monkeypatch.delenv("GUEST_STATUS_API_TOKEN_SHA256", raising=False)
    else:
        monkeypatch.setenv("GUEST_STATUS_API_TOKEN_SHA256", environment_hash)

    rollout_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    assert rollout_app.config["GUEST_STATUS_API_TOKEN_SHA256"] == (environment_hash or "")

    with rollout_app.app_context():
        try:
            db.session.add(User(
                username="rollout-admin",
                password_hash=generate_password_hash("test-password"),
                role="admin",
                realname="Rollout Admin",
            ))
            db.session.commit()
            client = rollout_app.test_client()

            assert client.get("/health").status_code == 200
            assert client.get("/login").status_code == 200
            login = client.post(
                "/login",
                data={"username": "rollout-admin", "password": "test-password"},
            )
            assert login.status_code == 302
            assert client.get("/guest/list").status_code == 200

            response = client.post("/api/v1/guest-status", json={"code": "unknown"})
            assert response.status_code == 503
            assert response.get_json() == {"error": "Die API ist nicht konfiguriert."}
            assert client.get("/health").status_code == 200
            assert client.get("/guest/list").status_code == 200
        finally:
            db.session.remove()
            db.drop_all()


@pytest.mark.parametrize(
    "payload",
    [{}, {"code": None}, {"code": 123}, {"code": True},
     {"code": " "}, {"code": "a" * 256}, [], "code"],
)
def test_invalid_payload_is_rejected(client, api_headers, payload):
    response = client.post("/api/v1/guest-status", json=payload, headers=api_headers)
    assert response.status_code == 400
    assert response.is_json


@pytest.mark.parametrize(
    "body,content_type",
    [("{", "application/json"), ("code=abc", "application/x-www-form-urlencoded")],
)
def test_non_json_and_malformed_json_are_rejected(client, api_headers, body, content_type):
    response = client.post(
        "/api/v1/guest-status", data=body, content_type=content_type, headers=api_headers
    )
    assert response.status_code == 400
    assert response.is_json


def test_lookup_failure_does_not_expose_internal_details(client, app, api_headers, monkeypatch):
    with app.app_context():
        def fail_lookup(*args, **kwargs):
            raise RuntimeError("private database connection details")

        monkeypatch.setattr(db.session, "get", fail_lookup)
        response = client.post(
            "/api/v1/guest-status", json={"code": "unknown"}, headers=api_headers
        )
    assert response.status_code == 500
    assert response.get_json() == {"error": "Interner Serverfehler."}
    assert response.headers["Cache-Control"] == "no-store"
