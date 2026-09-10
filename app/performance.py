import re
import time
from uuid import uuid4

from flask import Flask, g, has_request_context, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
SESSION_TIMER_KEY = "pfotenregister_commit_started_at"
_session_events_registered = False


def _get_metrics():
    """Return request metrics when instrumentation is active."""
    if not has_request_context():
        return None
    return getattr(g, "performance_metrics", None)


def _before_commit(session: Session) -> None:
    """Start timing a database commit in the current request."""
    if _get_metrics() is not None:
        session.info[SESSION_TIMER_KEY] = time.perf_counter()


def _after_commit(session: Session) -> None:
    """Record a completed database commit in the current request."""
    started_at = session.info.pop(SESSION_TIMER_KEY, None)
    metrics = _get_metrics()
    if started_at is None or metrics is None:
        return
    metrics["commit_count"] += 1
    metrics["commit_ms"] += (time.perf_counter() - started_at) * 1000


def _clear_commit_timer(session: Session) -> None:
    """Discard commit timing when a transaction rolls back."""
    session.info.pop(SESSION_TIMER_KEY, None)


def _register_session_events() -> None:
    """Register SQLAlchemy session timing hooks once per process."""
    global _session_events_registered
    if _session_events_registered:
        return
    event.listen(Session, "before_commit", _before_commit)
    event.listen(Session, "after_commit", _after_commit)
    event.listen(Session, "after_rollback", _clear_commit_timer)
    _session_events_registered = True


def _register_engine_events(app: Flask, engine: Engine) -> None:
    """Register query timing hooks for one SQLAlchemy engine."""
    if getattr(engine, "_pfotenregister_performance_monitoring", False):
        return

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._pfotenregister_query_started_at = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        started_at = getattr(context, "_pfotenregister_query_started_at", None)
        metrics = _get_metrics()
        if started_at is None or metrics is None:
            return
        duration_ms = (time.perf_counter() - started_at) * 1000
        metrics["query_count"] += 1
        metrics["query_ms"] += duration_ms
        if duration_ms >= app.config["SLOW_QUERY_THRESHOLD_MS"]:
            operation = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else "UNKNOWN"
            app.logger.warning(
                "slow_database_query request_id=%s endpoint=%s operation=%s duration_ms=%.1f",
                metrics["request_id"],
                request.endpoint or "unknown",
                operation,
                duration_ms,
            )

    engine._pfotenregister_performance_monitoring = True


def register_performance_monitoring(app: Flask, database: SQLAlchemy) -> None:
    """Log request, query, and commit timings without request payloads."""
    _register_session_events()
    with app.app_context():
        _register_engine_events(app, database.engine)

    @app.before_request
    def start_request_timer():
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_request_id
            if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else uuid4().hex
        )
        g.performance_metrics = {
            "started_at": time.perf_counter(),
            "request_id": request_id,
            "query_count": 0,
            "query_ms": 0.0,
            "commit_count": 0,
            "commit_ms": 0.0,
        }

    @app.after_request
    def log_request_performance(response):
        metrics = _get_metrics()
        if metrics is None:
            return response
        total_ms = (time.perf_counter() - metrics["started_at"]) * 1000
        is_slow = total_ms >= app.config["SLOW_REQUEST_THRESHOLD_MS"]
        should_log = is_slow or (
            app.config["PERFORMANCE_LOG_ALL_WRITES"]
            and request.method in WRITE_METHODS
        )
        if should_log:
            log = app.logger.warning if is_slow else app.logger.info
            log(
                "request_performance request_id=%s method=%s endpoint=%s status=%d "
                "total_ms=%.1f db_query_count=%d db_query_ms=%.1f "
                "db_commit_count=%d db_commit_ms=%.1f slow=%s",
                metrics["request_id"],
                request.method,
                request.endpoint or "unknown",
                response.status_code,
                total_ms,
                metrics["query_count"],
                metrics["query_ms"],
                metrics["commit_count"],
                metrics["commit_ms"],
                str(is_slow).lower(),
            )
        response.headers["X-Request-ID"] = metrics["request_id"]
        response.headers["Server-Timing"] = (
            f'app;dur={total_ms:.1f}, db;dur={metrics["query_ms"]:.1f}, '
            f'commit;dur={metrics["commit_ms"]:.1f}'
        )
        return response
