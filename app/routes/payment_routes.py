from datetime import datetime

from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required

from ..db import db_cursor
from ..helpers import roles_required, get_form_value

payment_bp = Blueprint("payment", __name__)


def save_payment_entry(guest_id, futter_betrag, zubehoer_betrag, kommentar):
    today = datetime.now().date()
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO zahlungshistorie (gast_id, zahlungstag, futter_betrag, zubehoer_betrag, kommentar)
            VALUES (%s, %s, %s, %s, %s)
        """,
            (guest_id, today, futter_betrag, zubehoer_betrag, kommentar),
        )


@payment_bp.route("/guest/<guest_id>/payment_direct", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def payment_guest_direct(guest_id):
    futter_betrag = request.form.get("futter_betrag", type=float, default=0.0)
    zubehoer_betrag = request.form.get("zubehoer_betrag", type=float, default=0.0)
    kommentar = get_form_value("kommentar")
    today = datetime.now().date()
    save_payment_entry(guest_id, futter_betrag, zubehoer_betrag, kommentar)

    flash("Zahlung erfolgreich erfasst.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))