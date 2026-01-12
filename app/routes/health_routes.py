from flask import Blueprint

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET", "HEAD","POST"])
def health():
    return "", 200

