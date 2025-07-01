from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required

from ..helpers import roles_required, get_form_value
from ..models import db, FoodHistory, PaymentHistory

food_bp = Blueprint("food", __name__)

@food_bp.route("/guest/<guest_id>/create_food_entry", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def create_food_entry(guest_id):
    comment = get_form_value("comment") or request.args.get("comment")
    futter_betrag = request.form.get("futter_betrag", type=float, default=0.0)
    zubehoer_betrag = request.form.get("zubehoer_betrag", type=float, default=0.0)
    zahlung_comment = get_form_value("zahlungKommentar_futter")
    entry = FoodHistory(gast_id=guest_id, futtertermin=datetime.today().date(), notiz=comment)
    db.session.add(entry)
    if futter_betrag or zubehoer_betrag:
        payment = PaymentHistory(
            gast_id=guest_id,
            zahlungstag=datetime.today().date(),
            futter_betrag=futter_betrag,
            zubehoer_betrag=zubehoer_betrag,
            kommentar=zahlung_comment,
        )
        db.session.add(payment)
        msg = "Futterverteilung und Zahlung gespeichert."
    else:
        msg = "Futterverteilung gespeichert."
    db.session.commit()
    flash(msg, "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@food_bp.route("/feed_entry/<int:entry_id>/edit", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def edit_feed_entry(entry_id):
    entry = FoodHistory.query.get_or_404(entry_id)
    entry.futtertermin = request.form.get("futtertermin", entry.futtertermin)
    entry.notiz = get_form_value("notiz")
    db.session.commit()
    flash("Eintrag aktualisiert.", "success")
    return redirect(url_for("guest.view_guest", guest_id=entry.gast_id))


@food_bp.route("/feed_entry/<int:entry_id>/delete", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def delete_feed_entry(entry_id):
    entry = FoodHistory.query.get_or_404(entry_id)
    guest_id = entry.gast_id
    db.session.delete(entry)
    db.session.commit()
    flash("Eintrag gelöscht.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))
