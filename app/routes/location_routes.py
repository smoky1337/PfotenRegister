from datetime import datetime

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from ..helpers import roles_required
from ..models import db, DropOffLocation


location_bp = Blueprint("location", __name__, url_prefix="/locations")


@location_bp.route("/", methods=["GET"])
@roles_required("admin", "editor")
@login_required
def map_view():
    locations = DropOffLocation.query.order_by(DropOffLocation.created_on.desc()).all()
    serialized = [loc.to_dict() for loc in locations]
    return render_template("locations/map.html", locations=locations, location_payload=serialized, title="Standorte")


@location_bp.route("/api", methods=["GET"])
@roles_required("admin", "editor")
@login_required
def list_locations():
    locations = DropOffLocation.query.order_by(DropOffLocation.name.asc()).all()
    return jsonify([loc.to_dict() for loc in locations])


@location_bp.route("/api", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def create_location():
    def as_bool(val, default=True):
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes", "on")

    data = request.get_json(force=True)
    required_fields = ("name", "address", "latitude", "longitude", "location_type")
    if not all(data.get(field) for field in required_fields):
        return jsonify({"error": "Bitte Name, Adresse, Typ und Koordinaten angeben."}), 400

    last_emptied = None
    if data.get("last_emptied"):
        try:
            last_emptied = datetime.strptime(data["last_emptied"], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Ungültiges Datum für 'Zuletzt geleert'."}), 400

    location = DropOffLocation(
        name=data["name"].strip(),
        address=data["address"].strip(),
        city=data.get("city"),
        latitude=float(data["latitude"]),
        longitude=float(data["longitude"]),
        location_type=data.get("location_type", "dropbox"),
        responsible_person=data.get("responsible_person"),
        last_emptied=last_emptied,
        comments=data.get("comments"),
        active=as_bool(data.get("active"), True),
    )
    db.session.add(location)
    db.session.commit()
    return jsonify(location.to_dict()), 201


@location_bp.route("/api/<int:location_id>", methods=["PATCH"])
@roles_required("admin", "editor")
@login_required
def update_location(location_id):
    location = DropOffLocation.query.get_or_404(location_id)
    data = request.get_json(force=True)
    def as_bool(val, default=False):
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes", "on")

    if "name" in data and data["name"]:
        location.name = data["name"].strip()
    if "address" in data and data["address"]:
        location.address = data["address"].strip()
    if "city" in data:
        location.city = data["city"]
    if "location_type" in data:
        location.location_type = data["location_type"]
    if "responsible_person" in data:
        location.responsible_person = data["responsible_person"]
    if "comments" in data:
        location.comments = data["comments"]
    if "active" in data:
        location.active = as_bool(data.get("active"))
    if "latitude" in data and data["latitude"]:
        location.latitude = float(data["latitude"])
    if "longitude" in data and data["longitude"]:
        location.longitude = float(data["longitude"])
    if "last_emptied" in data:
        if data["last_emptied"]:
            try:
                location.last_emptied = datetime.strptime(data["last_emptied"], "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "Ungültiges Datum für 'Zuletzt geleert'."}), 400
        else:
            location.last_emptied = None

    db.session.commit()
    return jsonify(location.to_dict())


@location_bp.route("/api/<int:location_id>/empty", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def empty_location(location_id):
    location = DropOffLocation.query.get_or_404(location_id)
    location.last_emptied = datetime.today().date()
    db.session.commit()
    return jsonify(location.to_dict())


@location_bp.route("/api/<int:location_id>", methods=["DELETE"])
@roles_required("admin", "editor")
@login_required
def delete_location(location_id):
    location = DropOffLocation.query.get_or_404(location_id)
    db.session.delete(location)
    db.session.commit()
    return jsonify({"deleted": True, "id": location_id})
