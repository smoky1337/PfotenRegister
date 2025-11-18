from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from ..helpers import add_changelog, roles_required, get_form_value, user_has_access, is_different
from ..models import db, Guest, Animal, FieldRegistry, FoodTag

animal_bp = Blueprint("animal", __name__, url_prefix="/animals")


@animal_bp.route("/<int:animal_id>/edit", methods=["GET"])
@roles_required("admin", "editor")
@login_required
def edit_animal(animal_id):
    animal = Animal.query.filter_by(id=animal_id).first()
    guest = animal.guest
    fields = (
        FieldRegistry.query
        .filter(FieldRegistry.model_name == "Animal")
        .filter(FieldRegistry.globally_visible == True)
        .all()
    )
    visible_fields = {}
    for f in fields:
        can_view = user_has_access(f.visibility_level)
        can_edit = user_has_access(f.editability_level)
        # Field is relevant if user can at least see or edit it
        if not (can_view or can_edit):
            continue
        visible_fields[f.field_name] = {
            "label": f.ui_label or f.field_name,
            # read_only if user can only see but not edit
            "read_only": can_view and not can_edit,
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


@animal_bp.route("/register", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def register_animal():
    guest_id = request.args.get("guest_id") or request.form.get("guest_id")
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


@animal_bp.route("/<int:animal_id>/update", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def update_animal(animal_id):
    old_animal = Animal.query.get(animal_id)
    guest_id = old_animal.guest_id
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


    for field in fields:
        name = field.field_name
        can_view = user_has_access(field.visibility_level)
        can_edit = user_has_access(field.editability_level)

        # Skip fields the user cannot see or edit at all
        if not (can_view or can_edit):
            continue

        # Do not allow updates on view-only fields
        if not can_edit:
            continue

        if name not in request.form:
            continue
        new_value = get_form_value(name)
        old_value = getattr(old_animal, name, None)
        if new_value != old_value:
            column = Animal.__table__.columns.get(name)
            if isinstance(column.type, db.Boolean):
                new_value = new_value.lower() in ("1", "true", "ja", "yes")

            if is_different(new_value, old_value):
                setattr(old_animal, name, new_value)
                label = field.ui_label or name
                changes.append(f"{label} geändert")

    old_animal.updated_on = datetime.now()

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
    next_url = request.args.get('next') or request.headers.get('Referer') or url_for("guest.view_guest",
                                                                                     guest_id=guest_id)
    return redirect(next_url)


@animal_bp.route("/<int:animal_id>/edit_note", methods=["POST"])
@login_required
def edit_animal_note(animal_id):
    new_notes = request.form.get("notizen", "").strip()
    animal = Animal.query.get_or_404(animal_id)
    animal.note = new_notes
    animal.updated_on = datetime.now()
    db.session.commit()
    flash("Tiernotizen aktualisiert.", "success")
    next_url = request.args.get('next') or request.headers.get('Referer') or url_for("guest.view_guest",
                                                                                     guest_id=animal.guest_id)
    return redirect(next_url)


@animal_bp.route("/<int:animal_id>/delete", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def delete_animal(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    guest_id = animal.guest_id
    Animal.query.filter_by(id=animal_id).delete()
    db.session.commit()
    add_changelog(guest_id, "delete", f"Tier gelöscht (ID: {animal_id})")
    flash("Tier wurde gelöscht.", "success")
    next_url = request.args.get('next') or request.headers.get('Referer') or url_for("guest.view_guest",
                                                                                     guest_id=guest_id)
    return redirect(next_url)


@animal_bp.route("/<int:animal_id>/edit_tags", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def edit_animal_tags(animal_id):
    # Load guest and animal
    animal = Animal.query.filter_by(id=animal_id).first_or_404()

    # Read selected tag IDs from form
    selected_ids = request.form.getlist("tag_ids")
    # Query tag objects and assign
    selected_tags = FoodTag.query.filter(FoodTag.id.in_(selected_ids)).all()
    animal.food_tags = selected_tags

    db.session.commit()
    flash("Tags aktualisiert", "success")
    # Redirect back to referring page or guest view
    next_url = request.args.get("next") or request.headers.get("Referer") or url_for(
        "guest.view_guest", guest_id=animal.guest_id
    )
    return redirect(next_url)


@animal_bp.route("/list", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def list_animals():
    animals = (
        db.session
        .query(
            Animal.id.label('animal_id'),
            Animal.died_on.label('animal_died_on'),
            Guest.id.label('guest_id'),
            Guest.number.label('guest_number'),
            Guest.firstname.label('guest_firstname'),
            Guest.lastname.label('guest_lastname'),
            Animal.status.label('animal_status'),
            Animal.name.label('animal_name'),
            Animal.species.label('animal_species'),
            Animal.breed.label('animal_breed'),
        )
        .join(Guest, Animal.guest_id == Guest.id)
        .order_by(Guest.number)
        .all()
    )

    return render_template(
        "list_animals.html",
        animals=animals,
        title="Tierliste",
    )
