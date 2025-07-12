from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from ..models import db, Guest, Animal, FieldRegistry
from ..helpers import add_changelog, roles_required, get_form_value, get_visible_fields, user_has_access

animal_bp = Blueprint("animal", __name__)


@animal_bp.route("/guest/<guest_id>/<int:animal_id>/edit", methods=["GET"])
@roles_required("admin", "editor")
@login_required
def edit_animal(guest_id, animal_id):
    guest = Guest.query.get(guest_id)
    animal = Animal.query.filter_by(guest_id=guest_id, id=animal_id).first() if guest else None
    visible_fields = {
        f.field_name: f.ui_label or f.field_name
        for f in FieldRegistry.query.all()
        if user_has_access(f.visibility_level)
    }
    if not guest:
        flash("Gast nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))

    if guest and animal:
        return render_template(
            "edit_animal.html",
            guest=guest,
            animal=animal,
            scanning_enabled=False,
            visible_fields=visible_fields,
        )
    else:
        flash("Tier nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))


@animal_bp.route("/guest/register/animal", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def register_animal():
    guest_id = request.args.get("guest_id") or request.form.get("guest_id")
    visible_fields = get_visible_fields(Animal)
    if not guest_id:
        flash("Fehler - Gast ID fehlt - bitte Administrator kontaktieren!", "danger")
        return redirect(url_for("guest.index"))
    if request.method == "POST":
        now = datetime.now()
        fields = (
            FieldRegistry.query
            .filter(FieldRegistry.model_name == "Animal")
            .filter(FieldRegistry.globally_visible == True)
            .all()
        )
        data = {}
        for field in fields:
            if user_has_access(field.visibility_level):
                value = get_form_value(field.field_name)
                if value is not None:
                    # Special handling for booleans
                    column_type = getattr(Animal.__table__.columns.get(field.field_name), "type", None)
                    if isinstance(column_type, db.Boolean):
                        value = value.lower() in ("1", "true", "ja", "yes")
                    data[field.field_name] = value


        animal = Animal(
            created_on=now,
            updated_on=now,
            **data
        )
        db.session.add(animal)
        db.session.commit()
        add_changelog(
            guest_id,
            "create",
            f"Tier '{animal.name}' hinzugefügt",
        )
        return redirect(url_for("guest.view_guest", guest_id=guest_id))
    else:
        guest = Guest.query.get(guest_id)
        guest_name = f"{guest.firstname} {guest.lastname}" if guest else "Unbekannt"
        visible_fields = {
            f.field_name: f.ui_label or f.field_name
            for f in FieldRegistry.query.all()
            if user_has_access(f.visibility_level)
        }
        return render_template(
            "register_animal.html",
            guest_id=guest_id,
            guest_name=guest_name,
            visible_fields=visible_fields,
        )


@animal_bp.route("/guest/<guest_id>/<int:animal_id>/update", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def update_animal(guest_id, animal_id):
    old_animal = Animal.query.get(animal_id)
    if not old_animal:
        flash("Tier nicht gefunden.", "danger")
        return redirect(url_for("guest.view_guest", guest_id=guest_id))

    fields = (
        FieldRegistry.query
        .filter(FieldRegistry.model_name == "Animal")
        .filter(FieldRegistry.globally_visible == True)
        .all()
    )

    changes = []

    def is_different(new, old):
        if new in (None, "") and old in (None, ""):
            return False
        return str(new) != str(old)

    for field in fields:
        name = field.field_name
        if not user_has_access(field.visibility_level):
            continue
        if name not in request.form:
            continue
        new_value = get_form_value(name)
        old_value = getattr(old_animal, name, None)

        if is_different(new_value, old_value):
            setattr(old_animal, name, new_value)
            label = field.ui_label or name
            changes.append(f"{label} geändert")

    old_animal.aktualisiert_am = datetime.now()

    if not changes:
        flash("Keine Änderungen am Tier erkannt.", "info")
        return redirect(url_for("guest.view_guest", guest_id=guest_id))

    db.session.commit()
    add_changelog(
        guest_id,
        "update",
        f"Tier '{old_animal.name}' bearbeitet: " + ", ".join(changes),
    )
    flash("Tierdaten erfolgreich aktualisiert.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@animal_bp.route("/guest/<guest_id>/edit_animal_notes/<int:animal_id>", methods=["POST"])
@login_required
def edit_animal_notes(guest_id, animal_id):
    new_notes = request.form.get("notizen", "").strip()
    animal = Animal.query.get_or_404(animal_id)
    animal.note = new_notes
    animal.updated_on = datetime.now()
    db.session.commit()
    flash("Tiernotizen aktualisiert.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@animal_bp.route("/guest/<guest_id>/<int:animal_id>/delete", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def delete_animal(guest_id, animal_id):
    Animal.query.filter_by(id=animal_id).delete()
    db.session.commit()
    add_changelog(guest_id, "delete", f"Tier gelöscht (ID: {animal_id})")
    flash("Tier wurde gelöscht.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))
