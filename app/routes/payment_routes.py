from datetime import datetime

from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required

from ..db import db_cursor
from ..helpers import roles_required, get_form_value

payment_bp = Blueprint("payment", __name__)


@payment_bp.route("/guest/<guest_id>/create_food_entry", methods=["POST"])
@login_required
def create_food_entry(guest_id):
    notiz = get_form_value("comment")
    zahlungKommentar_futter = get_form_value("zahlungKommentar_futter")
    futter_betrag = request.form.get("futter_betrag", type=float, default=0.0)
    zubehoer_betrag = request.form.get("zubehoer_betrag", type=float, default=0.0)
    with db_cursor() as cursor:
        today = datetime.now().date()
        cursor.execute(
            "INSERT INTO futterhistorie (gast_id, futtertermin, notiz) VALUES (%s, %s, %s)",
            (guest_id, today, notiz),
        )
        if futter_betrag > 0.0 or zubehoer_betrag > 0.0:
            cursor.execute(
                """
                INSERT INTO zahlungshistorie (gast_id, zahlungstag, futter_betrag, zubehoer_betrag, kommentar)
                VALUES (%s, %s, %s, %s, %s)
            """,
                (guest_id, today, futter_betrag, zubehoer_betrag, zahlungKommentar_futter),
            )

    if futter_betrag > 0.0 or zubehoer_betrag > 0.0:
        flash("Futterverteilung und Zahlung gespeichert.", "success")
    else:
        flash("Futterverteilung gespeichert.", "success")

    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@payment_bp.route("/feed_entry/<int:entry_id>/edit", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def edit_feed_entry(entry_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM futterhistorie WHERE entry_id = %s", (entry_id,))
        entry = cursor.fetchone()
        if not entry:
            flash("Eintrag nicht gefunden.", "danger")
            return redirect(url_for("guest.index"))

        if request.method == "POST":
            new_date = request.form.get("futtertermin")
            new_note = request.form.get("notiz", "")
            cursor.execute(
                """
                UPDATE futterhistorie SET futtertermin = %s, notiz = %s WHERE entry_id = %s
            """,
                (new_date, new_note, entry_id),
            )
            flash("Futtereintrag aktualisiert.", "success")
            return redirect(url_for("guest.view_guest", guest_id=entry["gast_id"]))
        return None


@payment_bp.route("/feed_entry/<int:entry_id>/delete", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def delete_feed_entry(entry_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT gast_id FROM futterhistorie WHERE entry_id = %s", (entry_id,))
        entry = cursor.fetchone()
        if not entry:
            flash("Eintrag nicht gefunden.", "danger")
            return redirect(url_for("guest.index"))

        cursor.execute("DELETE FROM futterhistorie WHERE entry_id = %s", (entry_id,))
        flash("Futtereintrag gelöscht.", "success")
        return redirect(url_for("guest.view_guest", guest_id=entry["gast_id"]))


@payment_bp.route("/guest/<guest_id>/payment_direct", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def payment_guest_direct(guest_id):
    futter_betrag = request.form.get("futter_betrag", type=float, default=0.0)
    zubehoer_betrag = request.form.get("zubehoer_betrag", type=float, default=0.0)
    kommentar = get_form_value("kommentar")
    today = datetime.now().date()

    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO zahlungshistorie (gast_id, zahlungstag, futter_betrag, zubehoer_betrag, kommentar)
            VALUES (%s, %s, %s, %s, %s)
        """,
            (guest_id, today, futter_betrag, zubehoer_betrag, kommentar),
        )

    flash("Zahlung erfolgreich erfasst.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))
