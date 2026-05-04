from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy.sql.sqltypes import Boolean, Date, Enum, Text

from ..helpers import (
    add_changelog,
    roles_required,
    get_form_value,
    user_has_access,
    is_different,
    get_guest_list_sort_args,
    guest_list_sort_order,
)
from ..models import db, Guest, Animal, FieldRegistry, FoodTag

animal_bp = Blueprint("animal", __name__, url_prefix="/animals")

ANIMAL_CREATE_GROUPS = {
    "species": ("profile", "identity"),
    "breed": ("profile", "identity"),
    "name": ("profile", "identity"),
    "sex": ("profile", "identity"),
    "color": ("profile", "identity"),
    "castrated": ("profile", "identity"),
    "identification": ("profile", "identity"),
    "birthdate": ("profile", "identity"),
    "status": ("profile", "admin"),
    "tax_until": ("profile", "admin"),
    "weight_or_size": ("care", "health"),
    "illnesses": ("care", "health"),
    "allergies": ("care", "health"),
    "food_type": ("care", "supply"),
    "complete_care": ("care", "supply"),
    "last_seen": ("care", "health"),
    "veterinarian": ("care", "health"),
    "food_amount_note": ("care", "supply"),
    "note": ("care", "notes"),
}
ANIMAL_CREATE_STEP_LAYOUT = [
    {
        "id": "profile",
        "title": "Tierprofil",
        "description": "Grunddaten und Verwaltungsangaben für das Tier.",
        "sections": [
            {"id": "identity", "title": "Allgemeine Tierdaten"},
            {"id": "admin", "title": "Verwaltung"},
        ],
    },
    {
        "id": "care",
        "title": "Versorgung",
        "description": "Gesundheit, Futter und interne Versorgungshinweise.",
        "sections": [
            {"id": "health", "title": "Gesundheit"},
            {"id": "supply", "title": "Futter & Versorgung"},
            {"id": "notes", "title": "Interne Hinweise"},
        ],
    },
]
ANIMAL_EDIT_GROUPS = {
    "species": ("identity", 0),
    "breed": ("identity", 1),
    "name": ("identity", 2),
    "sex": ("identity", 3),
    "color": ("identity", 4),
    "castrated": ("identity", 5),
    "identification": ("identity", 6),
    "birthdate": ("identity", 7),
    "status": ("admin", 0),
    "tax_until": ("admin", 1),
    "died_on": ("admin", 2),
    "weight_or_size": ("health", 0),
    "illnesses": ("health", 1),
    "allergies": ("health", 2),
    "last_seen": ("health", 3),
    "veterinarian": ("health", 4),
    "food_type": ("supply", 0),
    "complete_care": ("supply", 1),
    "food_amount_note": ("supply", 2),
    "note": ("notes", 0),
}
ANIMAL_EDIT_SECTION_LAYOUT = [
    {"id": "identity", "title": "Tierprofil"},
    {"id": "health", "title": "Gesundheit"},
    {"id": "supply", "title": "Versorgung"},
    {"id": "admin", "title": "Verwaltung"},
    {"id": "notes", "title": "Interne Hinweise"},
    {"id": "additional", "title": "Weitere Angaben"},
]


def _get_animal_registry_fields():
    """Return visible animal registry fields in display order."""
    fields = (
        FieldRegistry.query
        .filter(FieldRegistry.model_name == "Animal")
        .filter(FieldRegistry.globally_visible == True)
        .order_by(FieldRegistry.display_order.asc(), FieldRegistry.field_name.asc())
        .all()
    )
    visible_fields = []
    for field in fields:
        can_view = user_has_access(field.visibility_level)
        can_edit = user_has_access(field.editability_level)
        if can_view or can_edit:
            visible_fields.append({"registry": field, "read_only": can_view and not can_edit})
    return visible_fields


def _default_animal_form_value(field_name):
    """Provide stable defaults for new animal records."""
    defaults = {
        "species": "Hund",
        "sex": "Unbekannt",
        "castrated": "Unbekannt",
        "status": "1",
        "food_type": "Misch",
        "complete_care": "Unbekannt",
    }
    return defaults.get(field_name, "")


def _build_animal_form_field(registry_field, form_values=None, instance=None, read_only=False):
    """Build a render-friendly field definition for animal create/edit forms."""
    form_values = form_values or {}
    field_name = registry_field.field_name
    column = Animal.__table__.columns.get(field_name)
    if column is None:
        return None

    if instance is not None:
        raw_value = getattr(instance, field_name, None)
        if isinstance(raw_value, bool):
            value = "1" if raw_value else "0"
        elif hasattr(raw_value, "isoformat"):
            value = raw_value.isoformat()
        elif raw_value is None:
            value = ""
        else:
            value = str(raw_value)
    else:
        value = form_values.get(field_name, _default_animal_form_value(field_name))

    input_type = "text"
    options = []
    if field_name == "status" or isinstance(column.type, Boolean):
        input_type = "select"
        options = [
            {"value": "1", "label": "Aktiv"},
            {"value": "0", "label": "Inaktiv"},
        ]
    elif isinstance(column.type, Enum):
        input_type = "select"
        options = [{"value": option, "label": option} for option in column.type.enums]
    elif isinstance(column.type, Date):
        input_type = "date"
    elif isinstance(column.type, Text):
        input_type = "textarea"
    elif "note" in field_name:
        input_type = "textarea"

    span = 12 if input_type == "textarea" or field_name in {"food_amount_note", "note", "illnesses", "allergies"} else 6
    help_text = None
    if field_name == "food_amount_note":
        help_text = (
            "Dieser Eintrag wird bei der Futterausgabe prominent angezeigt, "
            "zum Beispiel regelmäßige Mengen oder Kombinationen."
        )

    return {
        "name": field_name,
        "field_name": field_name,
        "label": registry_field.ui_label or field_name,
        "input_type": input_type,
        "options": options,
        "allow_blank": input_type == "select" and field_name not in {"species", "sex", "castrated", "status", "food_type", "complete_care"},
        "required": False,
        "value": value,
        "span": span,
        "read_only": read_only,
        "help_text": help_text,
    }


def _build_animal_registration_steps(form_values=None):
    """Assemble step-based animal registration sections based on field visibility."""
    form_values = form_values or {}
    steps = []
    section_lookup = {}

    for step_config in ANIMAL_CREATE_STEP_LAYOUT:
        step = {
            "id": step_config["id"],
            "title": step_config["title"],
            "description": step_config["description"],
            "sections": [],
        }
        for section_config in step_config["sections"]:
            section = {"id": section_config["id"], "title": section_config["title"], "fields": []}
            section_lookup[(step["id"], section["id"])] = section
            step["sections"].append(section)
        steps.append(step)

    for item in _get_animal_registry_fields():
        field = _build_animal_form_field(item["registry"], form_values=form_values)
        if not field:
            continue
        target_step, target_section = ANIMAL_CREATE_GROUPS.get(item["registry"].field_name, ("care", "notes"))
        section_lookup[(target_step, target_section)]["fields"].append(field)

    visible_steps = []
    for index, step in enumerate(steps, start=1):
        sections = [section for section in step["sections"] if section["fields"]]
        if sections:
            step["sections"] = sections
            step["number"] = len(visible_steps) + 1
            visible_steps.append(step)
    return visible_steps


def _build_animal_edit_sections(animal):
    """Assemble grouped edit sections for animal fields."""
    sections = {
        section["id"]: {"id": section["id"], "title": section["title"], "fields": []}
        for section in ANIMAL_EDIT_SECTION_LAYOUT
    }

    for item in _get_animal_registry_fields():
        field_name = item["registry"].field_name
        if field_name in ("id", "guest_id", "created_on", "updated_on"):
            continue
        field = _build_animal_form_field(item["registry"], instance=animal, read_only=item["read_only"])
        if not field:
            continue
        section_id, priority = ANIMAL_EDIT_GROUPS.get(field_name, ("additional", 999))
        field["priority"] = priority
        sections[section_id]["fields"].append(field)

    ordered_sections = []
    for section in ANIMAL_EDIT_SECTION_LAYOUT:
        current = sections[section["id"]]
        if current["fields"]:
            current["fields"].sort(key=lambda item: (item.get("priority", 999), item["label"].lower()))
            ordered_sections.append(current)
    return ordered_sections


@animal_bp.route("/<int:animal_id>/edit", methods=["GET"])
@roles_required("admin", "editor")
@login_required
def edit_animal(animal_id):
    """Render the animal edit form grouped by dynamic, visibility-aware sections."""
    animal = Animal.query.filter_by(id=animal_id).first()
    if not animal:
        flash("Tier nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))
    guest = animal.guest
    if not guest:
        flash("Gast nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))

    return render_template(
        "edit_animal.html",
        guest=guest,
        animal=animal,
        scanning_enabled=False,
        edit_sections=_build_animal_edit_sections(animal),
    )


@animal_bp.route("/register", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def register_animal():
    """Create an animal through a step-based, visibility-aware intake form."""
    guest_id = request.args.get("guest_id") or request.form.get("guest_id")
    if not guest_id:
        flash("Fehler - Gast ID fehlt - bitte Administrator kontaktieren!", "danger")
        return redirect(url_for("guest.index"))
    if request.method == "POST":
        now = datetime.now()
        data = {}
        for item in _get_animal_registry_fields():
            field = item["registry"]
            if item["read_only"]:
                continue
            value = get_form_value(field.field_name)
            if value is not None:
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
        return render_template(
            "register_animal.html",
            guest_id=guest_id,
            guest_name=guest_name,
            registration_steps=_build_animal_registration_steps(),
            initial_step=1,
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
    sort_by, sort_direction = get_guest_list_sort_args(request.args)
    current_filter = request.args.get("filter", "all")
    if current_filter not in {"all", "active", "inactive", "deceased"}:
        current_filter = "all"
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
        .order_by(*guest_list_sort_order(sort_by, sort_direction), Animal.name.asc())
        .all()
    )

    return render_template(
        "list_animals.html",
        animals=animals,
        current_sort=sort_by,
        current_sort_direction=sort_direction,
        current_filter=current_filter,
        title="Tierliste",
    )
