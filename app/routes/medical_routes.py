from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func

from ..helpers import add_changelog, get_form_value, roles_required, get_guest_list_sort_args, guest_list_sort_order
from ..models import Attachment, Animal, Guest, MedicalEvent, MedicalEventAttachment, db

medical_bp = Blueprint("medical", __name__, url_prefix="/medical")


def _parse_date(field_name):
    """Parse ISO date values from forms and treat blanks as None."""
    raw_value = request.form.get(field_name, "").strip()
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_amount(field_name):
    """Parse decimal-like form values while accepting German commas."""
    raw_value = request.form.get(field_name, "").strip()
    if not raw_value:
        return 0.0
    normalized_value = raw_value.replace(",", ".")
    try:
        return float(normalized_value)
    except ValueError:
        return 0.0


def _get_guest_attachments(guest_id, attachment_ids):
    """Limit attachment assignments to documents already owned by the guest."""
    if not attachment_ids:
        return []
    unique_ids = sorted({int(att_id) for att_id in attachment_ids if str(att_id).isdigit()})
    if not unique_ids:
        return []
    return (
        Attachment.query.filter(
            Attachment.id.in_(unique_ids),
            Attachment.owner_id == guest_id,
        )
        .order_by(Attachment.filename.asc())
        .all()
    )


def _sync_event_attachments(event, attachments):
    """Replace attachment links for a medical event in one step."""
    event.attachment_links.clear()
    for attachment in attachments:
        event.attachment_links.append(MedicalEventAttachment(attachment=attachment))


def _populate_medical_event(event, guest_id):
    """Apply validated form values to a medical event instance."""
    animal_id = request.form.get("animal_id", type=int)
    animal = Animal.query.filter_by(id=animal_id, guest_id=guest_id).first()
    if not animal:
        return None, "Bitte ein Tier dieses Gastes auswählen."

    title = get_form_value("title")
    if not title:
        return None, "Bitte einen Titel für den medizinischen Vorgang angeben."

    event.guest_id = guest_id
    event.animal_id = animal.id
    event.title = title
    event.event_type = request.form.get("event_type") or "Behandlung"
    event.status = request.form.get("status") or "Geplant"
    event.priority = request.form.get("priority") or "Mittel"
    event.planned_for = _parse_date("planned_for")
    event.started_on = _parse_date("started_on")
    event.completed_on = _parse_date("completed_on")
    event.follow_up_on = _parse_date("follow_up_on")
    event.veterinarian = get_form_value("veterinarian") or animal.veterinarian
    event.description = get_form_value("description")
    event.estimated_cost = _parse_amount("estimated_cost")
    event.actual_cost = _parse_amount("actual_cost")
    event.paid_amount = _parse_amount("paid_amount")
    event.notes = get_form_value("notes")
    return animal, None


@medical_bp.route("/guest/<guest_id>/create", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def create_medical_event(guest_id):
    """Create a guest-linked medical event and optionally link guest documents."""
    guest = Guest.query.get_or_404(guest_id)
    medical_event = MedicalEvent()
    animal, error_message = _populate_medical_event(medical_event, guest.id)
    if error_message:
        flash(error_message, "warning")
        return redirect(url_for("guest.view_guest", guest_id=guest.id))

    attachments = _get_guest_attachments(guest.id, request.form.getlist("attachment_ids"))
    db.session.add(medical_event)
    db.session.flush()
    _sync_event_attachments(medical_event, attachments)
    db.session.commit()
    add_changelog(guest.id, "medical", f"Medizinischer Vorgang '{medical_event.title}' für Tier '{animal.name}' erstellt")
    flash("Medizinischer Vorgang gespeichert.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest.id, _anchor="medical"))


@medical_bp.route("/<int:event_id>/edit", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def edit_medical_event(event_id):
    """Update a medical event and replace its linked documents."""
    medical_event = MedicalEvent.query.get_or_404(event_id)
    animal, error_message = _populate_medical_event(medical_event, medical_event.guest_id)
    if error_message:
        flash(error_message, "warning")
        return redirect(url_for("guest.view_guest", guest_id=medical_event.guest_id))

    attachments = _get_guest_attachments(medical_event.guest_id, request.form.getlist("attachment_ids"))
    _sync_event_attachments(medical_event, attachments)
    medical_event.updated_on = datetime.utcnow()
    db.session.commit()
    add_changelog(
        medical_event.guest_id,
        "medical",
        f"Medizinischen Vorgang '{medical_event.title}' für Tier '{animal.name}' aktualisiert",
    )
    flash("Medizinischer Vorgang aktualisiert.", "success")
    return redirect(url_for("guest.view_guest", guest_id=medical_event.guest_id, _anchor="medical"))


@medical_bp.route("/<int:event_id>/delete", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def delete_medical_event(event_id):
    """Delete a medical event and its attachment links."""
    medical_event = MedicalEvent.query.get_or_404(event_id)
    guest_id = medical_event.guest_id
    title = medical_event.title
    db.session.delete(medical_event)
    db.session.commit()
    add_changelog(guest_id, "medical", f"Medizinischen Vorgang '{title}' gelöscht")
    flash("Medizinischer Vorgang gelöscht.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id, _anchor="medical"))


@medical_bp.route("/list", methods=["GET"])
@roles_required("admin", "editor")
@login_required
def list_medical_events():
    """List all medical events across guests and animals."""
    sort_by, sort_direction = get_guest_list_sort_args(request.args, {"name", "number", "date"})
    current_filter = request.args.get("filter", "all")
    if current_filter not in {"all", "planned", "active", "past"}:
        current_filter = "all"
    if sort_by == "date":
        date_column = func.coalesce(
            MedicalEvent.planned_for,
            MedicalEvent.started_on,
            MedicalEvent.completed_on,
            MedicalEvent.follow_up_on,
        )
        order_by = [
            date_column.desc() if sort_direction == "desc" else date_column.asc(),
            MedicalEvent.id.desc() if sort_direction == "desc" else MedicalEvent.id.asc(),
        ]
    else:
        order_by = [
            *guest_list_sort_order(sort_by, sort_direction),
            MedicalEvent.status.asc(),
            MedicalEvent.planned_for.asc(),
            MedicalEvent.started_on.desc(),
            MedicalEvent.id.desc(),
        ]
    medical_events = (
        db.session.query(
            MedicalEvent.id.label("id"),
            MedicalEvent.title.label("title"),
            MedicalEvent.event_type.label("event_type"),
            MedicalEvent.status.label("status"),
            MedicalEvent.priority.label("priority"),
            MedicalEvent.planned_for.label("planned_for"),
            MedicalEvent.started_on.label("started_on"),
            MedicalEvent.completed_on.label("completed_on"),
            MedicalEvent.follow_up_on.label("follow_up_on"),
            MedicalEvent.veterinarian.label("veterinarian"),
            MedicalEvent.actual_cost.label("actual_cost"),
            MedicalEvent.estimated_cost.label("estimated_cost"),
            Guest.id.label("guest_id"),
            Guest.number.label("guest_number"),
            Guest.firstname.label("guest_firstname"),
            Guest.lastname.label("guest_lastname"),
            Animal.id.label("animal_id"),
            Animal.name.label("animal_name"),
            Animal.species.label("animal_species"),
        )
        .join(Guest, MedicalEvent.guest_id == Guest.id)
        .join(Animal, MedicalEvent.animal_id == Animal.id)
        .order_by(*order_by)
        .all()
    )
    return render_template(
        "list_medical_events.html",
        medical_events=medical_events,
        current_sort=sort_by,
        current_sort_direction=sort_direction,
        current_filter=current_filter,
        title="Gesundheit",
    )
