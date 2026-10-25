import logging
import re
from datetime import date

from werkzeug.security import generate_password_hash

from app.models import Guest, User, db


def test_write_request_logs_database_and_request_timings(client, app, caplog):
    app.config["PERFORMANCE_LOG_ALL_WRITES"] = True
    app.config["SLOW_REQUEST_THRESHOLD_MS"] = 60_000
    caplog.set_level(logging.INFO, logger=app.logger.name)

    response = client.post(
        "/login",
        data={"username": "missing-user", "password": "wrong"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert "app;dur=" in response.headers["Server-Timing"]
    assert "db;dur=" in response.headers["Server-Timing"]
    assert "commit;dur=" in response.headers["Server-Timing"]
    performance_record = next(
        record for record in caplog.records
        if "request_performance" in record.getMessage()
    )
    message = performance_record.getMessage()
    assert "method=POST" in message
    assert "endpoint=auth.login" in message
    assert re.search(r"db_query_count=[1-9][0-9]*", message)
    assert "db_commit_count=0" in message


def test_invalid_incoming_request_id_is_replaced(client):
    response = client.get("/login", headers={"X-Request-ID": "invalid request id"})

    assert response.headers["X-Request-ID"] != "invalid request id"
    assert len(response.headers["X-Request-ID"]) == 32


def test_database_commit_is_included_in_request_metrics(client, app, caplog):
    with app.app_context():
        user = User(
            username="performance-admin",
            password_hash=generate_password_hash("password"),
            role="admin",
            realname="Performance Admin",
        )
        guest = Guest(
            id="PERF01",
            number="PERF001",
            firstname="Test",
            lastname="Messung",
            member_since=date.today(),
            created_on=date.today(),
            updated_on=date.today(),
        )
        db.session.add_all((user, guest))
        db.session.commit()
    login_response = client.post(
        "/login",
        data={"username": "performance-admin", "password": "password"},
    )
    assert login_response.status_code == 302

    caplog.clear()
    caplog.set_level(logging.INFO, logger=app.logger.name)
    response = client.post(
        "/guest/PERF01/edit_notes",
        data={"notizen": "Timing prüfen"},
    )

    assert response.status_code == 302
    performance_record = next(
        record for record in caplog.records
        if "request_performance" in record.getMessage()
    )
    message = performance_record.getMessage()
    assert "endpoint=guest.edit_notes" in message
    assert "db_commit_count=1" in message
    assert re.search(r"db_commit_ms=[0-9]+\.[0-9]", message)
