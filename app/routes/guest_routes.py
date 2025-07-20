from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_login import login_required
from sqlalchemy.sql.expression import func

from ..helpers import (
    generate_unique_code,
    get_food_history,
    add_changelog,
    roles_required,
    get_form_value,
    generate_guest_number, user_has_access, is_different
)
from ..models import db as sqlalchemy_db, Guest, Animal, Payments, Representative, ChangeLog, FoodHistory, FoodTag, \
    FieldRegistry
from ..reports import generate_gast_card_pdf

guest_bp = Blueprint("guest", __name__)


@guest_bp.route("/")
@login_required
def index():
    rows = Guest.query.order_by(Guest.lastname).with_entities(
        Guest.id, Guest.firstname, Guest.lastname
    ).all()
    guests = [{"id": r.id, "name": f"{r.firstname} {r.lastname}"} for r in rows]
    return render_template("start.html", guests=guests)


@guest_bp.route("/guest/search")
@login_required
def search_guests():
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return jsonify([])

    results = (
        Guest.query.filter(
            (Guest.firstname.ilike(f"%{query}%")) | (Guest.lastname.ilike(f"%{query}%"))
        )
        .order_by(Guest.lastname)
        .limit(10)
        .all()
    )

    return jsonify([
        {"id": g.id, "name": f"{g.firstname} {g.lastname}"} for g in results
    ])


@guest_bp.route("/guest/<guest_id>")
@login_required
def view_guest(guest_id):
    guest = Guest.query.get(guest_id)
    if guest:
        animals = Animal.query.filter_by(guest_id=guest.id).all()
        feed_history = get_food_history(guest.id)
        changelog = (
            ChangeLog.query.filter_by(guest_id=guest.id)
            .order_by(ChangeLog.change_timestamp.desc())
            .all()
        )
        payments = (
            Payments.query.filter_by(guest_id=guest.id)
            .order_by(Payments.created_on.desc())
            .all()
        )

        all_tags = (
            FoodTag.query.all()
        )
        # Build ordered list of visible Guest fields with UI labels
        all_fields = FieldRegistry.query.filter_by(model_name="Guest").all()
        # Filter by access and sort by display_order
        accessible = [f for f in all_fields if user_has_access(f.visibility_level)]
        accessible.sort(key=lambda f: f.display_order)
        # Prepare for template: name, label, inline flag, and order
        visible_fields_guest = [
            {
                "name": f.field_name,
                "label": f.ui_label or f.field_name,
                "show_inline": f.show_inline,
                "order": f.display_order,
            }
            for f in accessible
        ]

        # Build ordered list of visible Guest fields with UI labels
        all_fields = FieldRegistry.query.filter_by(model_name="Animal").all()
        # Filter by access and sort by display_order
        accessible = [f for f in all_fields if user_has_access(f.visibility_level)]
        accessible.sort(key=lambda f: f.display_order)
        # Prepare for template: name, label, inline flag, and order
        visible_fields_animal = [
            {
                "name": f.field_name,
                "label": f.ui_label or f.field_name,
                "show_inline": f.show_inline,
                "order": f.display_order,
            }
            for f in accessible
        ]

        representative = Representative.query.filter_by(guest_id=guest.id).first()

    else:
        animals = []
        changelog = []
        all_tags = []
        feed_history = []
        payments = []
        visible_fields_guest = []
        visible_fields_animal = []
        representative = []
    if guest:
        return render_template(
            "view_guest.html",
            visible_fields_guest=visible_fields_guest,
            visible_fields_animal=visible_fields_animal,
            guest=guest,
            all_tags=all_tags,
            representative=representative,
            animals=animals,
            changelog=changelog,
            feed_history=feed_history,
            scanning_enabled=True,
            datetime=datetime,
            current_time=datetime.today().date(),
            payments=payments,
            timedelta=timedelta,
        )
    else:
        flash("Gast nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))


@guest_bp.route("/guest/<guest_id>/edit", methods=["GET"])
@roles_required("admin", "editor")
@login_required
def edit_guest(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    representative = Representative.query.filter_by(guest_id=guest.id).first()

    visible_fields = {
        f.field_name: f.ui_label or f.field_name
        for f in FieldRegistry.query.filter_by(model_name="Guest").all()
        if user_has_access(f.visibility_level)
    }
    visible_fields_rep = {
        f"r_{f.field_name}": f.ui_label or f.field_name
        for f in FieldRegistry.query.filter_by(model_name="Representative").all()
        if user_has_access(f.visibility_level)
    }

    return render_template(
        "edit_guest.html",
        guest=guest,
        representative=representative,
        visible_fields=visible_fields,
        visible_fields_rep=visible_fields_rep,
        title="Gast bearbeiten"
    )


@guest_bp.route("/guest/list")
@login_required
def list_guests():
    guests = Guest.query.all()
    guest_ids = [g.id for g in guests]
    feed_history = {}
    if guest_ids:
        rows = (
            FoodHistory.query.with_entities(
                FoodHistory.guest_id, func.max(FoodHistory.distributed_on).label("latest")
            )
            .filter(FoodHistory.guest_id.in_(guest_ids))
            .group_by(FoodHistory.guest_id)
            .all()
        )
        for row in rows:
            feed_history[row.guest_id] = row.latest

    active_guests = []
    inactive_guests = []

    for g in guests:
        if g.status:
            active_guests.append(g)
        else:
            inactive_guests.append(g)
    return render_template(
        "list_guests.html",
        active_guests=active_guests,
        inactive_guests=inactive_guests,
        feed_history=feed_history,
        title="Gästeliste",
    )


@guest_bp.route("/guest/register", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def register_guest():
    if request.method == "POST":
        # Step 1: Collect field definitions from registry
        guest_fields = [
            f for f in FieldRegistry.query.filter_by(model_name="Guest").all()
            if user_has_access(f.visibility_level)
        ]
        # Step 2: Build form values dynamically
        guest_data = {}
        for field in guest_fields:
            field_name = field.field_name
            value = get_form_value(field_name)
            guest_data[field_name] = value if value != "" else None
        # Step 3: Mandatory fields check (adjust based on model constraints)
        required_fields = ["firstname", "lastname", "member_since"]
        if any(not guest_data.get(f) for f in required_fields):
            flash("Bitte fülle alle Pflichtfelder aus.", "danger")
            return redirect(url_for("guest.register_guest"))
        # Step 4: Check for duplicate
        existing = Guest.query.filter_by(
            firstname=guest_data.get("firstname"),
            lastname=guest_data.get("lastname"),
            address=guest_data.get("address")
        ).first()
        if existing:
            flash("Ein Gast mit diesem Namen und dieser Adresse existiert bereits.", "danger")
            return redirect(url_for("guest.register_guest"))
        # Step 5: Create guest
        guest_id = generate_unique_code(length=6)
        guest_data["id"] = guest_id
        guest_data["number"] = generate_guest_number()
        guest_data["created_on"] = datetime.now()
        guest_data["updated_on"] = datetime.now()
        guest_data["status"] = bool(int(guest_data.get("status")))
        guest = Guest(**guest_data)
        sqlalchemy_db.session.add(guest)
        # Step 6: Add representative if any data given
        rep_fields = [
            f for f in FieldRegistry.query.filter_by(model_name="Representativ").all()
            if user_has_access(f.visibility_level)
        ]
        rep_fields = ["r_" + t for t in rep_fields]
        if any(get_form_value(f) for f in rep_fields):
            representative = Representative(
                guest_id=guest_id,
                name=get_form_value("r_name") or None,
                phone=get_form_value("r_phone") or None,
                email=get_form_value("r_email") or None,
                address=get_form_value("r_address") or None,
            )
            sqlalchemy_db.session.add(representative)
        sqlalchemy_db.session.commit()
        add_changelog(guest_id, "create", "Gast erstellt")
        session["guests_changed"] = True
        action = request.form.get("action", "next")
        if action == "finish":
            flash("Gast wurde gespeichert.", "success")
            return redirect(url_for("guest.view_guest", guest_id=guest_id))
        return redirect(url_for("animal.register_animal", guest_id=guest_id))
    else:
        visible_fields = {
            f.field_name: f.ui_label or f.field_name
            for f in FieldRegistry.query.filter_by(model_name="Guest").all()
            if user_has_access(f.visibility_level)
        }
        visible_fields_rep = {
            f"r_{f.field_name}": f.ui_label or f.field_name
            for f in FieldRegistry.query.filter_by(model_name="Representative").all()
            if user_has_access(f.visibility_level)
        }
        return render_template(
            "register_guest.html",
            title="Gast Registrierung",
            visible_fields=visible_fields,
            visible_fields_rep=visible_fields_rep,
        )



# Neue, dynamische Update-Route für Gäste
@guest_bp.route("/guest/<guest_id>/update", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def update_guest(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    representative = Representative.query.filter_by(guest_id=guest.id).first()
    changes = []

    # Guest Felder dynamisch aktualisieren
    for field in FieldRegistry.query.filter_by(model_name="Guest").all():
        if not user_has_access(field.visibility_level):
            continue
        field_name = field.field_name
        # Skip non-updatable or required fields
        if field_name in ("id", "created_on", "updated_on", "member_since"):
            continue
        new_value = get_form_value(field_name)
        if new_value == "":
            new_value = None
        if hasattr(guest, field_name):
            old_value = getattr(guest, field_name)
            # Typkonvertierung
            if isinstance(old_value, bool):
                new_value = (str(new_value).lower() in ["true", "1", "on"])
            elif isinstance(old_value, int):
                try:
                    new_value = int(new_value)
                except Exception:
                    new_value = None
            elif isinstance(old_value, float):
                try:
                    new_value = float(new_value)
                except Exception:
                    new_value = None
            elif hasattr(old_value, "isoformat"):  # Datumstypen
                try:
                    new_value = datetime.strptime(new_value, "%Y-%m-%d").date()
                except Exception:
                    new_value = None
            # Änderung prüfen
            if is_different(new_value, old_value):
                setattr(guest, field_name, new_value)
                changes.append(f"{field.ui_label}")

    # Representative Felder dynamisch aktualisieren
    rep_fields = FieldRegistry.query.filter_by(model_name="Representative").all()
    rep_values = {}
    for field in rep_fields:
        if not user_has_access(field.visibility_level):
            continue
        field_name = field.field_name
        # Skip meta fields that should not be set via rep_values
        if field_name in ("guest_id", "id", "created_on", "updated_on"):
            continue
        form_field = f"r_{field_name}"
        new_value = get_form_value(form_field)
        if new_value == "":
            new_value = None
        rep_values[field_name] = new_value

    if representative:
        for field_name, new_value in rep_values.items():
            old_value = getattr(representative, field_name)
            if is_different(new_value, old_value):
                setattr(representative, field_name, new_value)
                changes.append(f"Vertreter: {field_name} geändert")
    elif any(rep_values.values()):
        # Nur wenn irgendein Feld ausgefüllt ist, neuen Vertreter anlegen
        new_rep = Representative(guest_id=guest.id, **rep_values)
        sqlalchemy_db.session.add(new_rep)
        changes.append("Vertreter hinzugefügt")

    if not changes:
        flash("Keine Änderungen erkannt.", "info")
        return redirect(url_for("guest.view_guest", guest_id=guest_id))

    guest.updated_on = datetime.now()
    sqlalchemy_db.session.commit()
    add_changelog(guest.id, "update", "Folgende Felder geändert: " + ", ".join(changes))
    session["guests_changed"] = True
    flash("Gastdaten erfolgreich aktualisiert.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@guest_bp.route("/guest/lookup")
@login_required
def guest_lookup():
    code = request.args.get("code", "").strip()
    if code:
        return redirect(url_for("guest.view_guest", guest_id=code))
    else:
        flash("Bitte einen Barcode eingeben.", "danger")
        return redirect(url_for("guest.index"))


@guest_bp.route("/guest/<guest_id>/print_card")
@login_required
def print_card(guest_id):
    guest = Guest.query.get(guest_id)
    if guest:
        pdf_bytes = generate_gast_card_pdf(guest.id)
        return send_file(
            pdf_bytes,
            as_attachment=True,
            download_name=f"{guest_id}.pdf",
            mimetype="application/pdf",
        )
    else:
        flash("Gast nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))


@guest_bp.route("/guest/<guest_id>/edit_notes", methods=["POST"])
@login_required
def edit_notes(guest_id):
    new_notes = request.form.get("notizen", "").strip()
    guest = Guest.query.get_or_404(guest_id)
    guest.notes = new_notes
    guest.updated_on = datetime.now()
    sqlalchemy_db.session.commit()
    flash("Notizen aktualisiert.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@guest_bp.route("/guest/<guest_id>/deactivate", methods=["POST"])
@roles_required("admin")
@login_required
def deactivate_guest(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    guest.status = False
    guest.updated_on = datetime.now()
    sqlalchemy_db.session.commit()
    add_changelog(guest_id, "update", "Gast deaktiviert")
    flash("Gast wurde deaktiviert.", "success")
    return redirect(url_for("guest.list_guests"))


@guest_bp.route("/guest/<guest_id>/activate", methods=["POST"])
@roles_required("admin")
@login_required
def activate_guest(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    guest.status = True
    guest.updated_on = datetime.now()
    sqlalchemy_db.session.commit()
    add_changelog(guest_id, "update", "Gast aktiviert")
    flash("Gast wurde aktiviert.", "success")
    return redirect(url_for("guest.list_guests"))


@guest_bp.route("/guest/<guest_id>/delete", methods=["POST"])
@roles_required("admin")
@login_required
def delete_guest(guest_id):
    if Payments.query.filter_by(guest_id=guest_id).first():
        flash("Gast ist Buchalterisch relevant und kann nicht gelöscht werden.", "danger")
        return redirect(url_for("guest.list_guests"))
    Animal.query.filter_by(guest_id=guest_id).delete()
    FoodHistory.query.filter_by(guest_id=guest_id).delete()
    ChangeLog.query.filter_by(guest_id=guest_id).delete()
    Guest.query.filter_by(id=guest_id).delete()
    sqlalchemy_db.session.commit()
    session["guests_changed"] = True
    flash("Gast wurde vollständig gelöscht.", "success")
    return redirect(url_for("guest.list_guests"))
