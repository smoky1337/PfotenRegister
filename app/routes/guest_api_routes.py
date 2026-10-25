import hashlib
import re
import secrets

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

from ..models import Guest, db


guest_api_bp = Blueprint("guest_api", __name__, url_prefix="/api/v1")


@guest_api_bp.before_request
def authenticate_guest_api():
    """Require the configured token independently of browser login sessions."""
    expected_hash = current_app.config.get("GUEST_STATUS_API_TOKEN_SHA256", "")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected_hash):
        return jsonify(error="Die API ist nicht konfiguriert."), 503

    authorization = request.headers.get("Authorization", "").split()
    if len(authorization) != 2 or authorization[0].lower() != "bearer":
        return _unauthorized_response()

    token_hash = hashlib.sha256(authorization[1].encode("utf-8")).hexdigest()
    if not secrets.compare_digest(token_hash, expected_hash.lower()):
        return _unauthorized_response()


def _unauthorized_response():
    """Return a consistent authentication error without a login redirect."""
    response = jsonify(error="Ungültiger oder fehlender API-Token.")
    response.status_code = 401
    response.headers["WWW-Authenticate"] = "Bearer"
    return response


@guest_api_bp.after_request
def prevent_guest_api_caching(response):
    """Keep guest status and authentication responses out of caches."""
    response.headers["Cache-Control"] = "no-store"
    return response


@guest_api_bp.errorhandler(Exception)
def handle_guest_api_error(error):
    """Keep API failures in JSON and hide internal exception details."""
    if isinstance(error, HTTPException):
        return jsonify(error="Ungültige API-Anfrage."), error.code
    current_app.logger.exception("Guest status API failed")
    db.session.rollback()
    return jsonify(error="Interner Serverfehler."), 500


@guest_api_bp.post("/guest-status")
def guest_status():
    """Expose only existence and active status for an exact guest code."""
    payload = request.get_json(silent=True)
    code = payload.get("code") if isinstance(payload, dict) else None
    if not isinstance(code, str) or not code.strip() or len(code.strip()) > 255:
        return jsonify(error="Bitte einen gültigen Gast-Code als JSON übergeben."), 400

    guest = db.session.get(Guest, code.strip())
    return jsonify(
        exists=guest is not None,
        active=guest.status_group == "active" if guest is not None else None,
    )
