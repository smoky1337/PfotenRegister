from datetime import datetime, timedelta
import hashlib

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, session, current_app
from flask_login import login_required, current_user
from sqlalchemy.sql.sqltypes import Boolean, Date, Enum, Text
from sqlalchemy.sql.expression import func

from ..helpers import (
    generate_unique_code,
    get_food_history,
    add_changelog,
    roles_required,
    get_form_value,
    generate_guest_number, user_has_access, is_different, build_reminder_alerts, send_guest_card_email, is_active
)
from ..models import db as sqlalchemy_db, Guest, Animal, Payment, Representative, ChangeLog, FoodHistory, FoodTag, \
    FieldRegistry, Message, User, Attachment, DropOffLocation, AccessoriesHistory, MedicalEvent
from ..reports import generate_gast_card_pdf, generate_multiple_gast_cards_pdf

guest_bp = Blueprint("guest", __name__)

GUEST_REQUIRED_CREATE_FIELDS = {"firstname", "lastname", "address", "indigence"}
GUEST_CREATE_GROUPS = {
    "firstname": ("basics", "identity"),
    "lastname": ("basics", "identity"),
    "birthdate": ("basics", "identity"),
    "gender": ("basics", "identity"),
    "status": ("basics", "organisation"),
    "member_since": ("basics", "organisation"),
    "member_until": ("basics", "organisation"),
    "address": ("basics", "contact"),
    "zip": ("basics", "contact"),
    "city": ("basics", "contact"),
    "phone": ("basics", "contact"),
    "mobile": ("basics", "contact"),
    "email": ("basics", "contact"),
    "indigence": ("support", "support"),
    "indigent_until": ("support", "support"),
    "documents": ("support", "documents"),
    "notes": ("optional", "notes"),
}
REPRESENTATIVE_CREATE_GROUPS = {
    "r_name": ("optional", "representative"),
    "r_phone": ("optional", "representative"),
    "r_email": ("optional", "representative"),
    "r_address": ("optional", "representative"),
}
GUEST_CREATE_STEP_LAYOUT = [
    {
        "id": "basics",
        "title": "Pflichtangaben",
        "description": "Stammdaten, Erreichbarkeit und organisatorische Angaben.",
        "sections": [
            {"id": "identity", "title": "Gastdaten"},
            {"id": "contact", "title": "Kontakt"},
            {"id": "organisation", "title": "Organisation"},
        ],
    },
    {
        "id": "support",
        "title": "Bedürftigkeit",
        "description": "Sozialdaten und zugehörige Hinweise oder Nachweise.",
        "sections": [
            {"id": "support", "title": "Bedürftigkeit"},
            {"id": "documents", "title": "Dokumentation"},
        ],
    },
    {
        "id": "optional",
        "title": "Optional",
        "description": "Vertretung, interne Hinweise und weitere sichtbare Angaben.",
        "sections": [
            {"id": "representative", "title": "Rechtlicher Vertreter"},
            {"id": "notes", "title": "Interne Angaben"},
            {"id": "additional", "title": "Weitere Angaben"},
        ],
    },
]
GUEST_EDIT_GROUPS = {
    "number": ("identity", 0),
    "firstname": ("identity", 1),
    "lastname": ("identity", 2),
    "birthdate": ("identity", 3),
    "gender": ("identity", 4),
    "status": ("organisation", 0),
    "member_since": ("organisation", 1),
    "member_until": ("organisation", 2),
    "address": ("contact", 0),
    "zip": ("contact", 1),
    "city": ("contact", 2),
    "phone": ("contact", 3),
    "mobile": ("contact", 4),
    "email": ("contact", 5),
    "indigence": ("support", 0),
    "indigent_until": ("support", 1),
    "documents": ("documents", 0),
    "notes": ("notes", 0),
}
REPRESENTATIVE_EDIT_GROUPS = {
    "r_name": ("representative", 0),
    "r_phone": ("representative", 1),
    "r_email": ("representative", 2),
    "r_address": ("representative", 3),
}
GUEST_EDIT_SECTION_LAYOUT = [
    {"id": "identity", "title": "Gastdaten"},
    {"id": "contact", "title": "Kontakt"},
    {"id": "organisation", "title": "Organisation"},
    {"id": "support", "title": "Bedürftigkeit"},
    {"id": "documents", "title": "Dokumentation"},
    {"id": "representative", "title": "Rechtlicher Vertreter"},
    {"id": "notes", "title": "Interne Angaben"},
    {"id": "additional", "title": "Weitere Angaben"},
]


def _get_registry_create_fields(model_name):
    """Return visible and editable registry fields for create forms in display order."""
    fields = (
        FieldRegistry.query.filter_by(model_name=model_name, globally_visible=True)
        .order_by(FieldRegistry.display_order.asc(), FieldRegistry.field_name.asc())
        .all()
    )
    visible_fields = []
    for field in fields:
        can_view = user_has_access(field.visibility_level)
        can_edit = user_has_access(field.editability_level)
        if can_view and can_edit:
            visible_fields.append(field)
    return visible_fields


def _build_create_field(model, registry_field, form_values=None, prefix=""):
    """Build a render-friendly field definition from the registry entry."""
    form_values = form_values or {}
    field_name = registry_field.field_name
    column = model.__table__.columns.get(field_name)
    if column is None:
        return None

    full_name = f"{prefix}{field_name}"
    value = form_values.get(full_name)
    if value is None:
        if full_name == "status":
            value = "1"
        elif full_name == "gender":
            value = "Unbekannt"
        elif full_name == "member_since":
            value = datetime.today().date().isoformat()
        else:
            value = ""

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
    elif "email" in field_name:
        input_type = "email"

    span = 12 if input_type == "textarea" or field_name in {"address", "documents", "notes"} else 6
    if full_name == "r_address":
        span = 12

    return {
        "name": full_name,
        "field_name": field_name,
        "label": registry_field.ui_label or field_name,
        "input_type": input_type,
        "options": options,
        "allow_blank": input_type == "select" and field_name not in {"status", "gender"},
        "required": field_name in GUEST_REQUIRED_CREATE_FIELDS and not prefix,
        "value": value,
        "span": span,
        "help_text": None,
    }


def _build_dispense_location_field(form_values, dispense_locations):
    """Expose the location assignment as a pseudo field in the first step."""
    return {
        "name": "dispense_location_id",
        "field_name": "dispense_location_id",
        "label": "Ausgabestandort",
        "input_type": "select",
        "options": [{"value": "", "label": "Bitte auswählen"}] + [
            {
                "value": str(location.id),
                "label": f"{location.name}{' – ' + location.address if location.address else ''}",
            }
            for location in dispense_locations
        ],
        "required": False,
        "value": form_values.get("dispense_location_id", ""),
        "span": 12,
        "help_text": "Nur Standorte mit Ausgabeflag werden hier angezeigt.",
    }


def _build_guest_registration_steps(form_values=None, locations_enabled=False, dispense_locations=None):
    """Assemble dynamic guest registration steps based on current field visibility."""
    form_values = form_values or {}
    dispense_locations = dispense_locations or []
    steps = []
    section_lookup = {}

    for step_config in GUEST_CREATE_STEP_LAYOUT:
        step = {
            "id": step_config["id"],
            "title": step_config["title"],
            "description": step_config["description"],
            "sections": [],
        }
        for section_config in step_config["sections"]:
            section = {
                "id": section_config["id"],
                "title": section_config["title"],
                "fields": [],
            }
            section_lookup[(step["id"], section["id"])] = section
            step["sections"].append(section)
        steps.append(step)

    for field in _get_registry_create_fields("Guest"):
        field_data = _build_create_field(Guest, field, form_values=form_values)
        if not field_data:
            continue
        target_step, target_section = GUEST_CREATE_GROUPS.get(field.field_name, ("optional", "additional"))
        section_lookup[(target_step, target_section)]["fields"].append(field_data)

    if locations_enabled:
        section_lookup[("basics", "organisation")]["fields"].append(
            _build_dispense_location_field(form_values, dispense_locations)
        )

    for field in _get_registry_create_fields("Representative"):
        field_data = _build_create_field(Representative, field, form_values=form_values, prefix="r_")
        if not field_data:
            continue
        target_step, target_section = REPRESENTATIVE_CREATE_GROUPS.get(field_data["name"], ("optional", "additional"))
        section_lookup[(target_step, target_section)]["fields"].append(field_data)

    visible_steps = []
    for step in steps:
        sections = [section for section in step["sections"] if section["fields"]]
        if sections:
            step["sections"] = sections
            visible_steps.append(step)

    for index, step in enumerate(visible_steps, start=1):
        step["number"] = index

    return visible_steps


def _render_register_guest_form(locations_enabled, dispense_locations, form_values=None, initial_step=1):
    """Render the guest registration form with dynamic sections and persisted values."""
    return render_template(
        "register_guest.html",
        title="Gast Registrierung",
        registration_steps=_build_guest_registration_steps(
            form_values=form_values,
            locations_enabled=locations_enabled,
            dispense_locations=dispense_locations,
        ),
        initial_step=initial_step,
        form_values=form_values or {},
    )


def _get_registry_edit_fields(model_name):
    """Return visible fields for edit forms with read-only state derived from the registry."""
    fields = (
        FieldRegistry.query.filter_by(model_name=model_name)
        .order_by(FieldRegistry.display_order.asc(), FieldRegistry.field_name.asc())
        .all()
    )
    visible_fields = []
    for field in fields:
        can_view = user_has_access(field.visibility_level)
        can_edit = user_has_access(field.editability_level)
        if not (can_view or can_edit):
            continue
        visible_fields.append({"registry": field, "read_only": can_view and not can_edit})
    return visible_fields


def _serialize_model_value(instance, field_name):
    """Convert model values into strings suitable for form controls."""
    value = getattr(instance, field_name, None)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _build_edit_field(model, registry_field, instance, read_only=False, prefix=""):
    """Build a render-friendly edit field from the registry and current model value."""
    column = model.__table__.columns.get(registry_field.field_name)
    if column is None:
        return None

    field = _build_create_field(model, registry_field, prefix=prefix)
    if not field:
        return None
    field["value"] = _serialize_model_value(instance, registry_field.field_name)
    field["read_only"] = read_only
    field["required"] = registry_field.field_name == "indigence" and not prefix
    if prefix == "r_" and registry_field.field_name == "address":
        field["span"] = 12
    return field


def _build_guest_edit_sections(guest, representative, locations_enabled=False, dispense_locations=None):
    """Assemble grouped edit sections for guest and representative data."""
    dispense_locations = dispense_locations or []
    sections = {
        section["id"]: {"id": section["id"], "title": section["title"], "fields": []}
        for section in GUEST_EDIT_SECTION_LAYOUT
    }

    for item in _get_registry_edit_fields("Guest"):
        field = _build_edit_field(Guest, item["registry"], guest, read_only=item["read_only"])
        if not field:
            continue
        section_id, priority = GUEST_EDIT_GROUPS.get(item["registry"].field_name, ("additional", 999))
        field["priority"] = priority
        sections[section_id]["fields"].append(field)

    if locations_enabled:
        location_field = _build_dispense_location_field(
            {"dispense_location_id": str(guest.dispense_location_id or "")},
            dispense_locations,
        )
        location_field["read_only"] = False
        location_field["priority"] = 99
        sections["organisation"]["fields"].append(location_field)

    representative_instance = representative or Representative()
    for item in _get_registry_edit_fields("Representative"):
        field = _build_edit_field(
            Representative,
            item["registry"],
            representative_instance,
            read_only=item["read_only"],
            prefix="r_",
        )
        if not field:
            continue
        section_id, priority = REPRESENTATIVE_EDIT_GROUPS.get(field["name"], ("additional", 999))
        field["priority"] = priority
        sections[section_id]["fields"].append(field)

    ordered_sections = []
    for section in GUEST_EDIT_SECTION_LAYOUT:
        current = sections[section["id"]]
        if current["fields"]:
            current["fields"].sort(key=lambda item: (item.get("priority", 999), item["label"].lower()))
            ordered_sections.append(current)
    return ordered_sections


@guest_bp.route("/")
@login_required
def index():
    rows = Guest.query.order_by(Guest.lastname).with_entities(
        Guest.id, Guest.firstname, Guest.lastname, Guest.number
    ).all()
    guests = [
        {"id": r.id, "code": r.id, "number": r.number, "name": f"{r.firstname} {r.lastname}"}
        for r in rows
    ]
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


def _build_shell_search_version():
    """Build a stable version hash for the shell search cache from searchable guest and animal fields."""
    guest_rows = (
        sqlalchemy_db.session.query(Guest.id, Guest.number, Guest.firstname, Guest.lastname)
        .order_by(Guest.id.asc())
        .all()
    )
    animal_rows = (
        sqlalchemy_db.session.query(Animal.id, Animal.guest_id, Animal.name)
        .order_by(Animal.id.asc())
        .all()
    )

    version_parts = []
    for guest in guest_rows:
        version_parts.append(
            f"g|{guest.id}|{guest.number or ''}|{guest.firstname or ''}|{guest.lastname or ''}"
        )
    for animal in animal_rows:
        version_parts.append(
            f"a|{animal.id}|{animal.guest_id or ''}|{animal.name or ''}"
        )

    digest = hashlib.sha1("\n".join(version_parts).encode("utf-8")).hexdigest()
    return digest


def _build_shell_search_entries():
    """Return shell search entries enriched with related animal names."""
    rows = (
        sqlalchemy_db.session.query(
            Guest.id,
            Guest.number,
            Guest.firstname,
            Guest.lastname,
            Animal.name.label("animal_name"),
        )
        .outerjoin(Animal, Animal.guest_id == Guest.id)
        .order_by(Guest.lastname.asc(), Guest.firstname.asc(), Animal.name.asc())
        .all()
    )

    guests_by_id = {}
    for row in rows:
        guest_entry = guests_by_id.setdefault(
            row.id,
            {
                "id": row.id,
                "code": row.id,
                "number": row.number or "",
                "name": f"{row.firstname or ''} {row.lastname or ''}".strip(),
                "animals": [],
            },
        )
        if row.animal_name and row.animal_name not in guest_entry["animals"]:
            guest_entry["animals"].append(row.animal_name)

    entries = []
    for guest in guests_by_id.values():
        animal_names = ", ".join(guest["animals"])
        entries.append(
            {
                "id": guest["id"],
                "code": guest["code"],
                "number": guest["number"],
                "name": guest["name"],
                "animals": guest["animals"],
                "search": " ".join(
                    part
                    for part in [guest["id"], guest["number"], guest["name"], animal_names]
                    if part
                ).lower(),
            }
        )

    return entries


@guest_bp.route("/guest/search-index/meta")
@login_required
def guest_search_index_meta():
    """Return a lightweight version token for the shell search cache."""
    return jsonify({"version": _build_shell_search_version()})


@guest_bp.route("/guest/search-index")
@login_required
def guest_search_index():
    """Return a guest and animal name index for the shell search field."""
    return jsonify({"version": _build_shell_search_version(), "entries": _build_shell_search_entries()})


@guest_bp.route("/guest/<guest_id>")
@login_required
def view_guest(guest_id):
    """Render the guest detail page with all related guest modules."""
    guest = Guest.query.get(guest_id)
    locations_enabled = is_active("locations") and is_active("locationGuestAssigment")
    if guest:
        animals = Animal.query.filter_by(guest_id=guest.id).all()
        messages = Message.query.filter_by(guest_id=guest.id).all()
        # Load guest documents
        guest_documents = Attachment.query.filter_by(owner_id=guest.id).all()

        feed_history = get_food_history(guest.id)
        changelog = (
            ChangeLog.query.filter_by(guest_id=guest.id)
            .order_by(ChangeLog.change_timestamp.desc())
            .all()
        )
        payments = (
            Payment.query.filter_by(guest_id=guest.id)
            .order_by(Payment.created_on.desc())
            .all()
        )
        accessories_history = (
            AccessoriesHistory.query.filter_by(guest_id=guest.id)
            .order_by(AccessoriesHistory.distributed_on.desc())
            .all()
        )
        medical_events = (
            MedicalEvent.query.filter_by(guest_id=guest.id)
            .order_by(
                MedicalEvent.status.asc(),
                MedicalEvent.planned_for.asc(),
                MedicalEvent.completed_on.desc(),
                MedicalEvent.id.desc(),
            )
            .all()
        )
        planned_medical_events = [event for event in medical_events if event.status == "Geplant"]
        active_medical_events = [event for event in medical_events if event.status == "Aktiv"]
        past_medical_events = [
            event for event in medical_events if event.status in ("Abgeschlossen", "Abgesagt")
        ]
        medical_events_by_attachment = {}
        for event in medical_events:
            for link in event.attachment_links:
                medical_events_by_attachment.setdefault(link.attachment_id, []).append(event)

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

        reminder_alerts = build_reminder_alerts(
            guest,
            animals=animals,
            representative=representative,
        )
        dispense_locations = (
            DropOffLocation.query.filter_by(is_dispense_location=True, active=True)
            .order_by(DropOffLocation.name.asc())
            .all()
            if locations_enabled else []
        )

        # Build ordered list of visible Guest fields with UI labels
        all_fields = FieldRegistry.query.filter_by(model_name="Representative").all()
        # Filter by access and sort by display_order
        accessible = [f for f in all_fields if user_has_access(f.visibility_level)]
        accessible.sort(key=lambda f: f.display_order)
        # Prepare for template: name, label, inline flag, and order
        visible_fields_representative = [
            {
                "name": f.field_name,
                "label": f.ui_label or f.field_name,
                "show_inline": f.show_inline,
                "order": f.display_order,
            }
            for f in accessible
        ]

    else:
        animals = []
        messages = []
        changelog = []
        guest_documents = []
        all_tags = []
        feed_history = []
        payments = []
        accessories_history = []
        medical_events = []
        planned_medical_events = []
        active_medical_events = []
        past_medical_events = []
        medical_events_by_attachment = {}
        visible_fields_guest = []
        visible_fields_animal = []
        visible_fields_representative = []
        representative = []
        reminder_alerts = []
    if guest:
        return render_template(
            "view_guest.html",
            visible_fields_guest=visible_fields_guest,
            visible_fields_animal=visible_fields_animal,
            messages=messages,
            guest_documents=guest_documents,
            guest=guest,
            all_tags=all_tags,
            visible_fields_representative=visible_fields_representative,
            representative=representative,
            animals=animals,
            changelog=changelog,
            feed_history=feed_history,
            accessories_history=accessories_history,
            medical_events=medical_events,
            planned_medical_events=planned_medical_events,
            active_medical_events=active_medical_events,
            past_medical_events=past_medical_events,
            medical_events_by_attachment=medical_events_by_attachment,
            scanning_enabled=True,
            datetime=datetime,
            current_time=datetime.today().date(),
            payments=payments,
            timedelta=timedelta,
            reminder_alerts=reminder_alerts,
            locations_enabled=locations_enabled,
            dispense_locations=dispense_locations,
        )
    else:
        flash("Gast nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))


@guest_bp.route("/guest/<guest_id>/report", methods=["GET"])
@login_required
def guest_report(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    representative = Representative.query.filter_by(guest_id=guest.id).first()

    def format_value(value):
        if value is None or value == "":
            return "-"
        if hasattr(value, "strftime"):
            return value.strftime("%d.%m.%Y")
        if isinstance(value, bool):
            return "Ja" if value else "Nein"
        return value

    def build_rows(model_name, instance, exclude_fields=None, multiline_fields=None):
        exclude_fields = exclude_fields or set()
        multiline_fields = multiline_fields or set()
        rows = []
        fields = FieldRegistry.query.filter_by(model_name=model_name).all()
        accessible = [f for f in fields if user_has_access(f.visibility_level)]
        accessible.sort(key=lambda f: f.display_order)
        for field in accessible:
            field_name = field.field_name
            if field_name in exclude_fields or not hasattr(instance, field_name):
                continue
            value = getattr(instance, field_name)
            rows.append(
                {
                    "name": field_name,
                    "label": field.ui_label or field_name,
                    "value": format_value(value),
                    "multiline": field_name in multiline_fields,
                }
            )
        return rows

    guest_rows = build_rows(
        "Guest",
        guest,
        exclude_fields={"id", "created_on", "updated_on", "guest_card_printed_on", "dispense_location_id"},
        multiline_fields={"notes", "documents"},
    )
    representative_rows = []
    if representative:
        representative_rows = build_rows(
            "Representative",
            representative,
            exclude_fields={"id", "guest_id"},
            multiline_fields=set(),
        )

    return render_template(
        "reports/guest_report.html",
        guest=guest,
        guest_rows=guest_rows,
        representative_rows=representative_rows,
        dispense_location=guest.dispense_location.name if guest.dispense_location else None,
        now=datetime.today(),
        current_user=current_user,
        title="Gastdatenübersicht",
    )


@guest_bp.route("/guest/<guest_id>/edit", methods=["GET"])
@roles_required("admin", "editor")
@login_required
def edit_guest(guest_id):
    """Render the guest edit form grouped by dynamic, visibility-aware sections."""
    guest = Guest.query.get_or_404(guest_id)
    representative = Representative.query.filter_by(guest_id=guest.id).first()
    locations_enabled = is_active("locations") and is_active("locationGuestAssigment")
    dispense_locations = (
        DropOffLocation.query.filter_by(is_dispense_location=True, active=True)
        .order_by(DropOffLocation.name.asc())
        .all()
        if locations_enabled else []
    )

    return render_template(
        "edit_guest.html",
        guest=guest,
        representative=representative,
        edit_sections=_build_guest_edit_sections(
            guest,
            representative,
            locations_enabled=locations_enabled,
            dispense_locations=dispense_locations,
        ),
        title="Gast bearbeiten"
    )


@guest_bp.route("/guest/list")
@login_required
def list_guests():
    guests = Guest.query.order_by(Guest.lastname.asc(), Guest.firstname.asc()).all()
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
    """Create a guest through a step-based, visibility-aware intake form."""
    locations_enabled = is_active("locations") and is_active("locationGuestAssigment")
    dispense_locations = (
        DropOffLocation.query.filter_by(is_dispense_location=True, active=True)
        .order_by(DropOffLocation.name.asc())
        .all()
        if locations_enabled else []
    )
    if request.method == "POST":
        guest_fields = _get_registry_create_fields("Guest")
        form_values = request.form.to_dict(flat=True)
        guest_data = {}
        for field in guest_fields:
            field_name = field.field_name
            value = get_form_value(field_name)
            guest_data[field_name] = value if value != "" else None

        required_fields = [
            field.field_name for field in guest_fields
            if field.field_name in GUEST_REQUIRED_CREATE_FIELDS
        ]
        missing_required = [
            field_name for field_name in required_fields
            if not guest_data.get(field_name)
        ]
        if missing_required:
            flash("Bitte fülle alle Pflichtfelder aus.", "danger")
            initial_step = 2 if "indigence" in missing_required else 1
            return _render_register_guest_form(
                locations_enabled,
                dispense_locations,
                form_values=form_values,
                initial_step=initial_step,
            )

        existing = None
        if guest_data.get("firstname") and guest_data.get("lastname") and guest_data.get("address"):
            existing = Guest.query.filter_by(
                firstname=guest_data.get("firstname"),
                lastname=guest_data.get("lastname"),
                address=guest_data.get("address")
            ).first()
        if existing:
            flash("Ein Gast mit diesem Namen und dieser Adresse existiert bereits.", "danger")
            return _render_register_guest_form(
                locations_enabled,
                dispense_locations,
                form_values=form_values,
                initial_step=1,
            )

        guest_id = generate_unique_code(length=6)
        if guest_data.get("member_since") is None:
            guest_data["member_since"] = datetime.today().date()
        guest_data["id"] = guest_id
        guest_data["number"] = generate_guest_number()
        guest_data["created_on"] = datetime.now()
        guest_data["updated_on"] = datetime.now()
        guest_data["status"] = bool(int(guest_data.get("status") or "1"))
        if locations_enabled:
            loc_id = request.form.get("dispense_location_id", type=int)
            if loc_id:
                disp_loc = DropOffLocation.query.filter_by(id=loc_id, is_dispense_location=True, active=True).first()
                if disp_loc:
                    guest_data["dispense_location_id"] = disp_loc.id
        guest = Guest(**guest_data)
        sqlalchemy_db.session.add(guest)

        representative_fields = _get_registry_create_fields("Representative")
        representative_form_fields = [f"r_{field.field_name}" for field in representative_fields]
        if any(get_form_value(field_name) for field_name in representative_form_fields):
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
        return _render_register_guest_form(
            locations_enabled,
            dispense_locations,
        )



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
        if not user_has_access(field.editability_level):
            continue
        field_name = field.field_name
        # Skip non-updatable or required fields
        if field_name in ("id", "number", "created_on", "updated_on", "member_since"):
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

    if is_active("locations") and is_active("locationGuestAssigment"):
        new_location_id = request.form.get("dispense_location_id", type=int)
        resolved_location_id = None
        if new_location_id:
            loc = DropOffLocation.query.filter_by(id=new_location_id, is_dispense_location=True, active=True).first()
            if loc:
                resolved_location_id = loc.id
        if is_different(resolved_location_id, guest.dispense_location_id):
            guest.dispense_location_id = resolved_location_id
            changes.append("Ausgabestandort")

    rep_fields = FieldRegistry.query.filter_by(model_name="Representative").all()
    rep_values = {}
    for field in rep_fields:
        if not user_has_access(field.visibility_level):
            continue
        if not user_has_access(field.editability_level):
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
    guest_number = request.args.get("guest_number", "").strip()

    if code:
        guest = Guest.query.get(code)
        if guest:
            return redirect(url_for("guest.view_guest", guest_id=guest.id))
        flash("Gast-Code nicht gefunden (Groß-/Kleinschreibung beachten).", "danger")
        return redirect(url_for("guest.index"))

    if guest_number:
        guest = (
            Guest.query.filter_by(number=guest_number)
            .order_by(Guest.updated_on.desc())
            .first()
        )
        if guest:
            return redirect(url_for("guest.view_guest", guest_id=guest.id))
        flash("Gastnummer nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))

    flash("Bitte einen Barcode/Gast-Code oder eine Gastnummer eingeben.", "danger")
    return redirect(url_for("guest.index"))


@guest_bp.route("/guest/<guest_id>/print_card")
@login_required
def print_card(guest_id):
    guest = Guest.query.get(guest_id)
    if guest:
        flip_backside = request.args.get("flip_backside", "").strip() in ("1", "true", "True", "on")
        pdf_bytes = generate_multiple_gast_cards_pdf([guest.id], double_sided=True, flip_backside=flip_backside)
        return send_file(
            pdf_bytes,
            as_attachment=True,
            download_name=f"{guest_id}.pdf",
            mimetype="application/pdf",
        )
    else:
        flash("Gast nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))


@guest_bp.route("/guest/<guest_id>/email_card", methods=["POST", "GET"])
@roles_required("admin", "editor")
@login_required
def email_card(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    email_status = current_app.config.get("SETTINGS", {}).get("emailEnabled", {})
    if email_status.get("value") != "Aktiv":
        flash("E-Mail Versand ist deaktiviert.", "warning")
        return redirect(url_for("guest.view_guest", guest_id=guest.id))
    ok, msg = send_guest_card_email(guest, current_app.config.get("SETTINGS", {}))
    if ok:
        guest.guest_card_emailed_on = datetime.today()
        sqlalchemy_db.session.commit()
        flash("Gästekarte per E-Mail versendet.", "success")
    else:
        flash(msg, "danger")
    return redirect(url_for("guest.view_guest", guest_id=guest.id))


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
    if Payment.query.filter_by(guest_id=guest_id).first():
        flash("Gast ist Buchalterisch relevant und kann nicht gelöscht werden.", "danger")
        return redirect(url_for("guest.list_guests"))
    Animal.query.filter_by(guest_id=guest_id).delete()
    FoodHistory.query.filter_by(guest_id=guest_id).delete()
    AccessoriesHistory.query.filter_by(guest_id=guest_id).delete()
    ChangeLog.query.filter_by(guest_id=guest_id).delete()
    Guest.query.filter_by(id=guest_id).delete()
    sqlalchemy_db.session.commit()
    session["guests_changed"] = True
    flash("Gast wurde vollständig gelöscht.", "success")
    return redirect(url_for("guest.list_guests"))


# region Messages
@guest_bp.route("/guest/<guest_id>/add_message", methods=["POST"])
@login_required
def add_message(guest_id):
    content = request.form.get("message", "").strip()
    msg = Message(
        created_on=datetime.today(),
        created_by=current_user.id,
        guest_id=guest_id,
        content=content,
    )
    sqlalchemy_db.session.add(msg)
    sqlalchemy_db.session.commit()
    flash("Nachricht hinterlegt!", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@guest_bp.route("/guest/<guest_id>/message/<message_id>/complete", methods=["POST"])
@login_required
def complete_message(guest_id, message_id):
    msg = Message.query.get_or_404(message_id)
    if str(msg.guest_id) != str(guest_id):
        abort(404)
    msg.completed = datetime.today()
    sqlalchemy_db.session.commit()

    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.accept_json
    )
    if wants_json:
        return jsonify(success=True, message_id=message_id)

    flash("Nachricht erledigt!", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


# below your other message routes:
@guest_bp.route("/messages/list")
@roles_required("admin", "editor")
@login_required
def list_messages():
    """
    Admin view: list all messages with guest info, creator, timestamps, and resolution status.
    """
    rows = (
        sqlalchemy_db.session
        .query(
            Message.id.label("msg_id"),
            Guest.id.label("guest_id"),
            Guest.firstname.label("guest_firstname"),
            Guest.lastname.label("guest_lastname"),
            Message.content.label("content"),
            Message.created_on.label("created_on"),
            User.realname.label("creator_name"),
            Message.completed.label("completed"),
        )
        .join(Guest, Message.guest_id == Guest.id)
        .join(User, Message.created_by == User.id)
        .order_by(Message.completed.asc(), Message.created_on.desc())
        .all()
    )
    return render_template("list_messages.html", messages=rows)

# endregion
