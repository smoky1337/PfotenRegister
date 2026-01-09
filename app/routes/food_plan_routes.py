from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from ..helpers import get_form_value, roles_required
from ..models import (
    Animal,
    DropOffLocation,
    FoodPlan,
    FoodPlanGuest,
    Guest,
    animal_food_tags,
    db,
)

food_plan_bp = Blueprint("food_plan", __name__, url_prefix="/food-plans")


def _foodplans_enabled() -> bool:
    return current_app.config.get("SETTINGS", {}).get("foodplans", {}).get("value") == "Aktiv"


@food_plan_bp.before_request
def _block_when_disabled():
    if not _foodplans_enabled():
        abort(404)


def _tagsystem_active() -> bool:
    return current_app.config.get("SETTINGS", {}).get("tagsystem", {}).get("value") == "Aktiv"


def _animal_is_active(animal: Animal) -> bool:
    return bool(animal.status) and animal.died_on is None


def _guest_is_active(guest: Guest) -> bool:
    return bool(guest.status)


def _normalize_text(value: Optional[str]) -> str:
    return (value or "").strip()


def _animal_tag_combo(animal: Animal) -> Tuple[Tuple[str, str], ...]:
    if not _tagsystem_active():
        return tuple()
    tags = sorted(
        ((t.name or "").strip(), (t.color or "").strip()) for t in (animal.food_tags or []) if (t.name or "").strip()
    )
    return tuple(tags)


def _combo_label(combo: Tuple[Tuple[str, str], ...]) -> str:
    if not combo:
        return "Ohne Tags"
    return " + ".join(name for name, _ in combo)


def _load_plan_or_404(plan_id: int) -> FoodPlan:
    plan = (
        FoodPlan.query.options(
            selectinload(FoodPlan.guests)
            .selectinload(FoodPlanGuest.guest)
            .selectinload(Guest.animals)
            .selectinload(Animal.food_tags)
        )
        .filter(FoodPlan.id == plan_id)
        .first()
    )
    if not plan:
        abort(404)
    return plan


def _bulk_add_guests(plan_id: int, guest_ids: List[str]) -> Tuple[int, int]:
    if not guest_ids:
        return 0, 0

    existing = {
        row.guest_id
        for row in FoodPlanGuest.query.with_entities(FoodPlanGuest.guest_id)
        .filter(FoodPlanGuest.food_plan_id == plan_id)
        .all()
    }
    to_add = [gid for gid in guest_ids if gid not in existing]

    if not to_add:
        return 0, len(guest_ids)

    max_sort = (
        db.session.query(db.func.max(FoodPlanGuest.sort_order))
        .filter(FoodPlanGuest.food_plan_id == plan_id)
        .scalar()
    )
    next_sort = int(max_sort or 0) + 1

    rows = [
        FoodPlanGuest(food_plan_id=plan_id, guest_id=gid, sort_order=next_sort + idx)
        for idx, gid in enumerate(to_add)
    ]
    db.session.add_all(rows)
    db.session.commit()
    return len(to_add), len(guest_ids) - len(to_add)


def _eligible_guest_ids(
    plan: FoodPlan,
    *,
    require_tagged_animals: bool = False,
    species: Optional[List[str]] = None,
    require_food_amount_note: bool = False,
) -> List[str]:
    query = Guest.query.filter(Guest.status == 1)
    if plan.location_id:
        query = query.filter(Guest.dispense_location_id == plan.location_id)

    needs_animals = require_tagged_animals or bool(species) or require_food_amount_note
    if needs_animals:
        query = query.join(Animal, Guest.id == Animal.guest_id).filter(
            Animal.status == 1, Animal.died_on.is_(None)
        )

    if species:
        query = query.filter(Animal.species.in_(species))

    if require_food_amount_note:
        query = query.filter(Animal.food_amount_note.isnot(None)).filter(Animal.food_amount_note != "")

    if require_tagged_animals:
        if not _tagsystem_active():
            return []
        query = query.join(animal_food_tags, animal_food_tags.c.animal_id == Animal.id)

    rows = (
        query.with_entities(Guest.id)
        .distinct()
        .order_by(Guest.lastname.asc(), Guest.firstname.asc(), Guest.number.asc(), Guest.id.asc())
        .all()
    )
    return [row.id for row in rows]


def _compute_plan(plan: FoodPlan) -> Dict:
    guest_entries: List[Dict] = []
    all_animals: List[Dict] = []

    for idx, pg in enumerate(plan.guests or []):
        guest = pg.guest
        if not guest or not _guest_is_active(guest):
            continue

        animals = [a for a in (guest.animals or []) if _animal_is_active(a)]
        animals.sort(key=lambda a: ((a.species or ""), (a.name or ""), a.id or 0))

        animal_entries = []
        for animal in animals:
            combo = _animal_tag_combo(animal)
            food_info = _normalize_text(animal.food_amount_note)
            allergies = _normalize_text(animal.allergies)

            animal_entry = {
                "id": animal.id,
                "species": animal.species,
                "name": animal.name,
                "combo": combo,
                "combo_label": _combo_label(combo),
                "tags": [{"name": n, "color": c} for n, c in combo],
                "food_info": food_info,
                "allergies": allergies,
            }
            animal_entries.append(animal_entry)
            all_animals.append(
                {
                    **animal_entry,
                    "guest_id": guest.id,
                    "guest_number": guest.number,
                    "guest_name": f"{guest.firstname} {guest.lastname}".strip(),
                }
            )

        guest_entries.append(
            {
                "id": guest.id,
                "number": guest.number,
                "name": f"{guest.firstname} {guest.lastname}".strip(),
                "dispense_location_id": guest.dispense_location_id,
                "note": _normalize_text(pg.note),
                "sort_order": pg.sort_order if pg.sort_order is not None else idx,
                "animals": animal_entries,
            }
        )

    guest_entries.sort(key=lambda g: (g["sort_order"], g["number"] or "", g["name"]))

    grouped: Dict[str, Dict[str, List[Dict]]] = {}
    grouped_by_combo: Dict[str, Dict[Tuple[Tuple[str, str], ...], List[Dict]]] = {}
    special: List[Dict] = []
    for entry in all_animals:
        species = entry.get("species") or "Unbekannt"
        combo = entry.get("combo") or tuple()
        combo_label = entry.get("combo_label") or "Ohne Tags"

        is_special = bool(entry.get("food_info") or entry.get("allergies"))
        has_tags = bool(combo)

        if is_special:
            special.append(entry)
        if not (has_tags and is_special):
            grouped.setdefault(species, {}).setdefault(combo_label, []).append(entry)
            grouped_by_combo.setdefault(species, {}).setdefault(combo, []).append(entry)

    for species, combos in grouped.items():
        for combo_label, entries in combos.items():
            entries.sort(key=lambda e: (e.get("guest_number") or "", e.get("guest_name") or "", e.get("name") or ""))

    grouped_sorted = []
    for species, combos in grouped_by_combo.items():
        combo_items = []
        for combo, entries in combos.items():
            entries.sort(key=lambda e: (e.get("guest_number") or "", e.get("guest_name") or "", e.get("name") or ""))
            combo_items.append(
                {
                    "combo": combo,
                    "combo_label": _combo_label(combo),
                    "tags": [{"name": n, "color": c} for n, c in combo],
                    "count": len(entries),
                    "entries": entries,
                }
            )
        combo_items.sort(key=lambda c: (-c["count"], (c["combo_label"] or "").lower()))
        grouped_sorted.append({"species": species, "combos": combo_items})
    grouped_sorted.sort(key=lambda s: (s["species"] or "").lower())

    combo_summary_by_species = []
    for species, combos in grouped_by_combo.items():
        summary_items = []
        for combo, entries in combos.items():
            summary_items.append(
                {
                    "combo": combo,
                    "combo_label": _combo_label(combo),
                    "tags": [{"name": n, "color": c} for n, c in combo],
                    "count": len(entries),
                }
            )
        summary_items.sort(key=lambda c: (-c["count"], (c["combo_label"] or "").lower()))
        combo_summary_by_species.append({"species": species, "combos": summary_items})
    combo_summary_by_species.sort(key=lambda s: (s["species"] or "").lower())

    special.sort(key=lambda e: (e.get("guest_number") or "", e.get("guest_name") or "", e.get("name") or ""))

    return {
        "mode": plan.mode or "guest_view",
        "general_note": _normalize_text(plan.general_note),
        "guests": guest_entries,
        "grouped": grouped,
        "grouped_sorted": grouped_sorted,
        "combo_summary_by_species": combo_summary_by_species,
        "special": special,
        "tagsystem_active": _tagsystem_active(),
    }


@food_plan_bp.route("/")
@login_required
@roles_required("admin", "editor")
def list_plans():
    plans = FoodPlan.query.order_by(FoodPlan.updated_on.desc()).all()
    return render_template("food_plans/list.html", title="Futterpläne", plans=plans)


@food_plan_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "editor")
def new_plan():
    locations = (
        DropOffLocation.query.filter_by(active=True)
        .order_by(DropOffLocation.name.asc())
        .all()
    )

    if request.method == "POST":
        title = _normalize_text(get_form_value("title")) or f"Futterplan {date.today().strftime('%d.%m.%Y')}"
        mode = get_form_value("mode") or "guest_view"
        status = get_form_value("status") or "Planen"
        location_id_raw = get_form_value("location_id")
        location_id = int(location_id_raw) if location_id_raw else None

        allowed_statuses = {"Planen", "Packen", "Gepackt", "Fertig"}
        allowed_modes = {"guest_view", "type_view", "type_summary"}
        plan = FoodPlan(
            title=title,
            mode=mode if mode in allowed_modes else "guest_view",
            status=status if status in allowed_statuses else "Planen",
            location_id=location_id,
            created_by_id=current_user.id,
        )
        db.session.add(plan)
        db.session.commit()
        flash("Futterplan erstellt.", "success")
        return redirect(url_for("food_plan.edit_plan", plan_id=plan.id))

    return render_template(
        "food_plans/new.html",
        title="Futterplan erstellen",
        locations=locations,
        status_choices=["Planen", "Packen", "Gepackt", "Fertig"],
    )


@food_plan_bp.route("/<int:plan_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "editor")
def edit_plan(plan_id: int):
    plan = _load_plan_or_404(plan_id)

    locations = (
        DropOffLocation.query.filter_by(active=True)
        .order_by(DropOffLocation.name.asc())
        .all()
    )

    if request.method == "POST":
        plan.title = _normalize_text(get_form_value("title")) or plan.title
        mode = get_form_value("mode") or plan.mode
        allowed_modes = {"guest_view", "type_view", "type_summary"}
        plan.mode = mode if mode in allowed_modes else plan.mode
        status = get_form_value("status") or plan.status
        allowed_statuses = {"Planen", "Packen", "Gepackt", "Fertig"}
        plan.status = status if status in allowed_statuses else plan.status

        location_id_raw = get_form_value("location_id")
        plan.location_id = int(location_id_raw) if location_id_raw else None

        plan.general_note = get_form_value("general_note")
        db.session.commit()
        flash("Futterplan gespeichert.", "success")
        return redirect(url_for("food_plan.edit_plan", plan_id=plan.id))

    search = _normalize_text(request.args.get("search"))
    candidates: List[Guest] = []
    if search:
        query = Guest.query.filter(Guest.status == 1)
        if plan.location_id:
            query = query.filter(Guest.dispense_location_id == plan.location_id)

        exact = query.filter((Guest.id == search) | (Guest.number == search)).first()
        if exact:
            candidates = [exact]
        else:
            like = f"%{search}%"
            candidates = (
                query.filter(
                    (Guest.number.ilike(like))
                    | (Guest.firstname.ilike(like))
                    | (Guest.lastname.ilike(like))
                )
                .order_by(Guest.lastname.asc(), Guest.firstname.asc())
                .limit(25)
                .all()
            )

    existing_guest_ids = {pg.guest_id for pg in (plan.guests or [])}
    return render_template(
        "food_plans/edit.html",
        title=f"Futterplan bearbeiten: {plan.title}",
        plan=plan,
        locations=locations,
        search=search,
        candidates=candidates,
        existing_guest_ids=existing_guest_ids,
        tagsystem_active=_tagsystem_active(),
        species_choices=["Hund", "Katze", "Vogel", "Nager", "Sonstige"],
        status_choices=["Planen", "Packen", "Gepackt", "Fertig"],
    )


@food_plan_bp.route("/<int:plan_id>/guests/add", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def add_guest(plan_id: int):
    plan = FoodPlan.query.options(selectinload(FoodPlan.guests)).filter_by(id=plan_id).first()
    if not plan:
        abort(404)

    guest_id = _normalize_text(get_form_value("guest_id"))
    if not guest_id:
        flash("Kein Gast ausgewählt.", "warning")
        return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))

    guest = Guest.query.filter_by(id=guest_id).first()
    if not guest or not _guest_is_active(guest):
        flash("Gast nicht gefunden oder inaktiv.", "danger")
        return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))

    existing = FoodPlanGuest.query.filter_by(food_plan_id=plan_id, guest_id=guest_id).first()
    if existing:
        flash("Gast ist bereits im Plan.", "info")
        return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))

    if plan.location_id and guest.dispense_location_id != plan.location_id:
        flash("Gast passt nicht zum ausgewählten Standort.", "warning")
        return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))

    max_sort = (
        db.session.query(db.func.max(FoodPlanGuest.sort_order))
        .filter(FoodPlanGuest.food_plan_id == plan_id)
        .scalar()
    )
    next_sort = int(max_sort or 0) + 1

    db.session.add(FoodPlanGuest(food_plan_id=plan_id, guest_id=guest_id, sort_order=next_sort))
    db.session.commit()
    flash("Gast hinzugefügt.", "success")
    return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))


@food_plan_bp.route("/<int:plan_id>/guests/bulk_add", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def bulk_add_guests(plan_id: int):
    plan = FoodPlan.query.filter_by(id=plan_id).first()
    if not plan:
        abort(404)

    action = _normalize_text(get_form_value("action"))
    selected_species = request.form.getlist("species")

    if action == "all_guests":
        guest_ids = _eligible_guest_ids(plan)
    elif action == "tagged_animals":
        guest_ids = _eligible_guest_ids(plan, require_tagged_animals=True)
        if not guest_ids and not _tagsystem_active():
            flash("Tagsystem ist deaktiviert.", "warning")
            return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))
    elif action == "species":
        allowed = {"Hund", "Katze", "Vogel", "Nager", "Sonstige"}
        species = [s for s in selected_species if s in allowed]
        if not species:
            flash("Keine Tierart ausgewählt.", "warning")
            return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))
        guest_ids = _eligible_guest_ids(plan, species=species)
    elif action == "food_amount_note":
        guest_ids = _eligible_guest_ids(plan, require_food_amount_note=True)
    else:
        flash("Unbekannte Aktion.", "danger")
        return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))

    added, already = _bulk_add_guests(plan_id, guest_ids)
    if added:
        msg = f"{added} Gäste hinzugefügt."
        if already:
            msg += f" ({already} bereits im Plan)"
        flash(msg, "success")
    else:
        flash("Keine neuen Gäste hinzugefügt.", "info")
    return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))


@food_plan_bp.route("/<int:plan_id>/guests/clear", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def clear_guests(plan_id: int):
    plan = FoodPlan.query.filter_by(id=plan_id).first()
    if not plan:
        abort(404)
    deleted = FoodPlanGuest.query.filter(FoodPlanGuest.food_plan_id == plan_id).delete(
        synchronize_session=False
    )
    db.session.commit()
    flash(f"{int(deleted or 0)} Gäste entfernt.", "success")
    return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))


@food_plan_bp.route("/<int:plan_id>/guests/<guest_id>/remove", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def remove_guest(plan_id: int, guest_id: str):
    row = FoodPlanGuest.query.filter_by(food_plan_id=plan_id, guest_id=guest_id).first()
    if not row:
        flash("Gast ist nicht im Plan.", "info")
        return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))
    db.session.delete(row)
    db.session.commit()
    flash("Gast entfernt.", "success")
    return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))


@food_plan_bp.route("/<int:plan_id>/guests/<guest_id>/note", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def update_guest_note(plan_id: int, guest_id: str):
    row = FoodPlanGuest.query.filter_by(food_plan_id=plan_id, guest_id=guest_id).first()
    if not row:
        abort(404)
    row.note = get_form_value("note")
    db.session.commit()
    flash("Notiz gespeichert.", "success")
    return redirect(url_for("food_plan.edit_plan", plan_id=plan_id))


@food_plan_bp.route("/<int:plan_id>/preview")
@login_required
@roles_required("admin", "editor")
def preview_plan(plan_id: int):
    plan = _load_plan_or_404(plan_id)
    computed = _compute_plan(plan)
    location_name = plan.location.name if plan.location else None
    return render_template(
        "food_plans/preview.html",
        title=f"Futterplan Vorschau: {plan.title}",
        plan=plan,
        computed=computed,
        location_name=location_name,
    )


@food_plan_bp.route("/<int:plan_id>/print")
@login_required
@roles_required("admin", "editor")
def print_plan(plan_id: int):
    plan = _load_plan_or_404(plan_id)
    computed = _compute_plan(plan)
    location_name = plan.location.name if plan.location else None
    return render_template(
        "reports/food_plan_report.html",
        plan=plan,
        computed=computed,
        location_name=location_name,
        now=datetime.utcnow(),
        title=f"Futterplan: {plan.title}",
    )


@food_plan_bp.route("/<int:plan_id>/delete", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def delete_plan(plan_id: int):
    plan = FoodPlan.query.filter_by(id=plan_id).first()
    if not plan:
        abort(404)
    db.session.delete(plan)
    db.session.commit()
    flash("Futterplan gelöscht.", "success")
    return redirect(url_for("food_plan.list_plans"))
