from datetime import datetime

from flask import Blueprint, request, redirect, url_for, flash, render_template
from flask_login import login_required

from ..helpers import roles_required, get_form_value
from ..models import db, Payments

payment_bp = Blueprint("payment", __name__)


def save_payment_entry(guest_id, food_amount, other_amount, comment, paid = True):
    today = datetime.now().date()
    payment = Payments(
        guest_id=guest_id,
        created_on=today,
        food_amount=food_amount,
        other_amount=other_amount,
        comment=comment,
        paid = paid,
        paid_on = today if paid else None
    )
    db.session.add(payment)
    db.session.commit()


@payment_bp.route("/payments/new_direct/<guest_id>/", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def payment_guest_direct(guest_id):
    food_amount = request.form.get("futter_betrag", type=float, default=0.0)
    other_amount = request.form.get("zubehoer_betrag", type=float, default=0.0)
    comment = get_form_value("kommentar")
    # Checkbox 'bezahlt' liefert nur einen Wert, wenn sie angehakt ist
    paid = "bezahlt" in request.form
    today = datetime.now().date()

    save_payment_entry(guest_id, food_amount, other_amount, comment, paid)

    flash("Zahlung erfolgreich erfasst.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@payment_bp.route("/payments/<int:payment_id>/create_offset", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def create_offset(payment_id):
    # Original payment lookup
    payment = Payments.query.filter_by(id=payment_id).first()
    guest_id = payment.guest_id
    if not payment:
        flash("Zahlung nicht gefunden.", "danger")
        return redirect(url_for("guest.view_guest", guest_id=guest_id))
    # Create offset entry reversing the original amounts
    comment = f"Ausgleich für Zahlung #{payment.id}"
    save_payment_entry(
        guest_id,
        -payment.food_amount,
        -payment.other_amount,
        comment,
        paid=True,
    )
    flash("Ausgleichszahlung erstellt.", "success")
    next_url = request.args.get('next') or request.headers.get('Referer') or url_for("guest.view_guest",
                                                                                     guest_id=guest_id)
    return redirect(next_url)


@payment_bp.route("/payments/<int:payment_id>/mark_as_paid/", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def mark_as_paid(payment_id):
    payment = Payments.query.filter_by(id=payment_id).first()
    if not payment:
        flash("Zahlung nicht gefunden.", "danger")
    else:
        if not payment.paid:
            payment.paid = True
            payment.paid_on = datetime.now().date()
            db.session.commit()
            flash("Zahlung als bezahlt markiert.", "success")
        else:
            flash("Zahlung ist bereits als bezahlt markiert.", "info")
    next_url = request.args.get('next') or request.headers.get('Referer') or url_for("guest.view_guest",
                                                                                     guest_id=payment.guest_id)
    return redirect(next_url)



@payment_bp.route("/guest/<guest_id>/delete/<int:payment_id>", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def delete_payment(guest_id, payment_id):
    payment = Payments.query.filter_by(id=payment_id, guest_id=guest_id).first()
    if not payment:
        flash("Zahlung nicht gefunden.", "danger")
    elif payment.paid:
        flash("Zahlung ist bereits gezahlt und kann nicht mehr gelöscht werden.", "info")
    else:
        flash("Zahlung erfolreich gelöscht", "success")
        db.session.delete(payment)
        db.session.commit()
    next_url = request.args.get('next') or request.headers.get('Referer') or url_for("guest.view_guest",
                                                                                     guest_id=guest_id)
    return redirect(next_url)


@payment_bp.route("/payments/list", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def list_payments():
    payments = Payments.query.all()

    return render_template(
        "list_payments.html",
        payments=payments,
        title="Zahlungsliste",
    )
