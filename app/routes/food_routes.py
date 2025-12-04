from datetime import datetime

from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required

from ..helpers import roles_required, get_form_value, is_active
from ..models import FoodTag
from ..models import db, FoodHistory, Setting, Guest, DropOffLocation
from ..routes.payment_routes import save_payment_entry

food_bp = Blueprint("food", __name__)


@food_bp.route("/guest/<guest_id>/create_food_entry", methods=["POST"])
@login_required
def create_food_entry(guest_id):
    notiz = get_form_value("notiz")
    zahlungKommentar_futter = get_form_value("zahlungKommentar_futter")
    futter_betrag = request.form.get("futter_betrag", type=float, default=0.0)
    zubehoer_betrag = request.form.get("zubehoer_betrag", type=float, default=0.0)
    locations_enabled = is_active("standorte")
    location_id = request.form.get("dispense_location_id", type=int) if locations_enabled else None

    today = datetime.now().date()
    guest = Guest.query.get(guest_id)

    resolved_location_id = None
    if locations_enabled and location_id:
        loc = DropOffLocation.query.filter_by(id=location_id, is_dispense_location=True).first()
        if loc and loc.active:
            resolved_location_id = loc.id

    new_entry = FoodHistory(
        guest_id=guest_id,
        distributed_on=today,
        comment=notiz,
        location_id=resolved_location_id,
    )
    db.session.add(new_entry)

    # Associate selected tags with this food history entry
    for form_key, tag_ids in request.form.lists():
        if form_key.startswith('tag_ids_'):
            for tag_id in tag_ids:
                tag = FoodTag.query.get(int(tag_id))
                if tag:
                    new_entry.distributed_tags.append(tag)

    payment_setting = Setting.query.filter_by(setting_key="zahlungen").first()
    print(payment_setting.value)
    payment_enabled = payment_setting and payment_setting.value =="Aktiv"

    if payment_enabled and (futter_betrag > 0.0 or zubehoer_betrag > 0.0):
        save_payment_entry(guest_id, futter_betrag, zubehoer_betrag, zahlungKommentar_futter)
        flash("Futterverteilung und Zahlung gespeichert.", "success")
    else:
        flash("Futterverteilung gespeichert.", "success")

    db.session.commit()


    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@food_bp.route("/feed_entry/<int:entry_id>/edit", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def edit_feed_entry(entry_id):
    entry = FoodHistory.query.get(entry_id)
    if not entry:
        flash("Eintrag nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))

    if request.method == "POST":
        new_date = request.form.get("futtertermin")
        new_note = request.form.get("notiz", "")
        locations_enabled = is_active("standorte")
        location_id = request.form.get("dispense_location_id", type=int) if locations_enabled else None
        entry.distributed_on = new_date
        entry.comment = new_note
        if locations_enabled:
            if location_id:
                loc = DropOffLocation.query.filter_by(id=location_id, is_dispense_location=True).first()
                entry.location_id = loc.id if loc else None
            else:
                entry.location_id = None
        db.session.commit()
        flash("Futtereintrag aktualisiert.", "success")
        return redirect(url_for("guest.view_guest", guest_id=entry.guest_id))
    return None


@food_bp.route("/feed_entry/<int:entry_id>/delete", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def delete_feed_entry(entry_id):
    entry = FoodHistory.query.get(entry_id)
    if not entry:
        flash("Eintrag nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))

    guest_id = entry.guest_id
    db.session.delete(entry)
    db.session.commit()
    flash("Futtereintrag gelöscht.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))
