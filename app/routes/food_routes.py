from datetime import datetime

from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required

from ..helpers import roles_required, get_form_value
from ..routes.payment_routes import save_payment_entry
from ..models import db, FoodHistory, Setting

food_bp = Blueprint("food", __name__)


@food_bp.route("/guest/<guest_id>/create_food_entry", methods=["POST"])
@login_required
def create_food_entry(guest_id):
    notiz = get_form_value("notiz")
    zahlungKommentar_futter = get_form_value("zahlungKommentar_futter")
    futter_betrag = request.form.get("futter_betrag", type=float, default=0.0)
    zubehoer_betrag = request.form.get("zubehoer_betrag", type=float, default=0.0)

    today = datetime.now().date()
    new_entry = FoodHistory(guest_id=guest_id, distributed_on=today, comment=notiz)
    db.session.add(new_entry)

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
        entry.futtertermin = new_date
        entry.notiz = new_note
        db.session.commit()
        flash("Futtereintrag aktualisiert.", "success")
        return redirect(url_for("guest.view_guest", guest_id=entry.gast_id))
    return None


@food_bp.route("/feed_entry/<int:entry_id>/delete", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def delete_feed_entry(entry_id):
    entry = FoodHistory.query.get(entry_id)
    if not entry:
        flash("Eintrag nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))

    guest_id = entry.gast_id
    db.session.delete(entry)
    db.session.commit()
    flash("Futtereintrag gelöscht.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))
