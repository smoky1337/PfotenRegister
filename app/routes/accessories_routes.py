from datetime import datetime

from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required

from ..helpers import roles_required, get_form_value, is_active
from ..models import db, Guest, DropOffLocation, AccessoriesHistory
from ..routes.payment_routes import save_payment_entry

accessories_bp = Blueprint("accessories", __name__)


@accessories_bp.route("/guest/<guest_id>/create_accessory", methods=["POST"])
@login_required
def create_accessory(guest_id):
    item = get_form_value("item")
    comment = get_form_value("comment")
    zahlungKommentar_zubehoer = get_form_value("zahlungKommentar_zubehoer")
    zubehoer_betrag = request.form.get("zubehoer_betrag", type=float, default=0.0)
    locations_enabled = is_active("locations")
    location_id = request.form.get("dispense_location_id", type=int) if locations_enabled else None

    if not item:
        flash("Bitte Zubehör angeben.", "warning")
        return redirect(url_for("guest.view_guest", guest_id=guest_id))

    guest = Guest.query.get(guest_id)
    if not guest:
        flash("Gast nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))

    resolved_location_id = None
    if locations_enabled and location_id:
        loc = DropOffLocation.query.filter_by(id=location_id, is_dispense_location=True).first()
        if loc and loc.active:
            resolved_location_id = loc.id

    new_entry = AccessoriesHistory(
        guest_id=guest_id,
        distributed_on=datetime.now().date(),
        item=item,
        comment=comment,
        location_id=resolved_location_id,
    )
    db.session.add(new_entry)
    db.session.flush()
    if is_active("payments") and zubehoer_betrag > 0.0:
        payment_comment = f"Zubehör-Ausgabe #{new_entry.id}"
        if zahlungKommentar_zubehoer:
            payment_comment = f"{payment_comment} — {zahlungKommentar_zubehoer}"
        save_payment_entry(guest_id, 0.0, zubehoer_betrag, payment_comment)
        flash("Zubehör und Zahlung gespeichert.", "success")
    else:
        flash("Zubehör gespeichert.", "success")
    db.session.commit()
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@accessories_bp.route("/accessory/<int:entry_id>/edit", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def edit_accessory(entry_id):
    entry = AccessoriesHistory.query.get(entry_id)
    if not entry:
        flash("Eintrag nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))

    item = get_form_value("item")
    comment = get_form_value("comment")
    new_date = request.form.get("distributed_on")
    locations_enabled = is_active("locations")
    location_id = request.form.get("dispense_location_id", type=int) if locations_enabled else None

    if not item:
        flash("Bitte Zubehör angeben.", "warning")
        return redirect(url_for("guest.view_guest", guest_id=entry.guest_id))

    entry.item = item
    entry.comment = comment
    if new_date:
        entry.distributed_on = new_date

    if locations_enabled:
        if location_id:
            loc = DropOffLocation.query.filter_by(id=location_id, is_dispense_location=True).first()
            entry.location_id = loc.id if loc and loc.active else None
        else:
            entry.location_id = None

    db.session.commit()
    flash("Zubehör aktualisiert.", "success")
    return redirect(url_for("guest.view_guest", guest_id=entry.guest_id))


@accessories_bp.route("/accessory/<int:entry_id>/delete", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def delete_accessory(entry_id):
    entry = AccessoriesHistory.query.get(entry_id)
    if not entry:
        flash("Eintrag nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))

    guest_id = entry.guest_id
    db.session.delete(entry)
    db.session.commit()
    flash("Zubehör gelöscht.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))
