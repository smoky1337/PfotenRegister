import re
from datetime import date, datetime

from flask import Blueprint, request, redirect, url_for, flash, render_template, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from ..helpers import roles_required, get_form_value, is_active
from ..models import (
    Animal,
    FoodDispensePlan,
    FoodTag,
    db,
    FoodHistory,
    Guest,
    DropOffLocation,
)
from ..routes.payment_routes import save_payment_entry

food_bp = Blueprint("food", __name__)


def _split_note_parts(note: str):
    if not note:
        return []
    parts = re.split(r"[;,\n]+", note)
    return [p.strip() for p in parts if p.strip()]


def _parse_plan_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _load_planning_guests(location_id, locations_enabled):
    base_query = (
        Guest.query.options(
            joinedload(Guest.animals).joinedload(Animal.food_tags),
            joinedload(Guest.dispense_location),
        )
        .filter(Guest.status.is_(True))
    )
    if locations_enabled and location_id:
        scoped = base_query.filter(Guest.dispense_location_id == location_id)
        scoped_guests = scoped.order_by(Guest.lastname.asc(), Guest.firstname.asc()).all()
        if scoped_guests:
            return scoped_guests, False
        return (
            base_query.order_by(Guest.lastname.asc(), Guest.firstname.asc()).all(),
            True,
        )
    return base_query.order_by(Guest.lastname.asc(), Guest.firstname.asc()).all(), False


def _build_plan_payload(guests, existing_payload, tags_enabled):
    existing_guest_map = {}
    if existing_payload and existing_payload.get("guests"):
        for entry in existing_payload["guests"]:
            gid = str(entry.get("id"))
            if gid:
                existing_guest_map[gid] = entry

    payload_guests = []
    seen_guest_ids = set()

    for guest in guests:
        gid = str(guest.id)
        seen_guest_ids.add(gid)
        existing_guest = existing_guest_map.get(gid, {})
        existing_animals = {
            str(a.get("id")): a for a in existing_guest.get("animals", [])
        } if existing_guest else {}

        animals_payload = []
        for animal in guest.animals:
            if not animal.status:
                continue
            aid = str(animal.id)
            existing_animal = existing_animals.get(aid, {})
            animal_include = existing_animal.get("include", True)
            tags = []
            if tags_enabled:
                tags = [
                    {"id": t.id, "name": t.name, "color": t.color}
                    for t in animal.food_tags
                ]
            note_text = animal.food_amount_note or animal.note or ""
            label_candidates = (
                [t["name"] for t in tags] if tags else _split_note_parts(note_text)
            )
            animals_payload.append(
                {
                    "id": animal.id,
                    "name": animal.name or "Unbenannt",
                    "species": animal.species or "Unbekannt",
                    "include": animal_include,
                    "tags": tags,
                    "notes": note_text,
                    "label_candidates": label_candidates,
                }
            )

        payload_guests.append(
            {
                "id": guest.id,
                "name": f"{guest.firstname} {guest.lastname}",
                "include": existing_guest.get("include", True),
                "animals": animals_payload,
                "location_id": guest.dispense_location_id,
                "location_name": guest.dispense_location.name if guest.dispense_location else None,
            }
        )

    # Preserve guests that might only exist in the stored payload (history)
    for gid, guest_data in existing_guest_map.items():
        if gid in seen_guest_ids:
            continue
        payload_guests.append(guest_data)

    return payload_guests


def _apply_selection(payload_guests, guest_ids, animal_keys):
    for guest in payload_guests:
        gid = str(guest.get("id"))
        include_guest = gid in guest_ids
        guest["include"] = include_guest
        for animal in guest.get("animals", []):
            key = f"{gid}:{animal.get('id')}"
            include_animal = key in animal_keys
            animal["include"] = include_guest and include_animal


def _compute_plan_summary(payload, tags_enabled):
    species_counts = {}
    tag_counts = {}
    included_guests = 0
    included_animals = 0

    for guest in payload.get("guests", []):
        if not guest.get("include", True):
            continue
        included_animals_for_guest = 0
        for animal in guest.get("animals", []):
            if not animal.get("include", True):
                continue
            included_animals += 1
            included_animals_for_guest += 1
            species = animal.get("species") or "Unbekannt"
            species_counts[species] = species_counts.get(species, 0) + 1

            labels = []
            tag_entries = animal.get("tags") or []
            label_candidates = animal.get("label_candidates") or []
            if tags_enabled and tag_entries:
                labels = label_candidates or [t.get("name") or "Ohne Tag" for t in tag_entries]
            else:
                labels = label_candidates or _split_note_parts(animal.get("notes", ""))

            if not labels:
                labels = ["Ohne Angabe"]
            for label in labels:
                tag_counts[label] = tag_counts.get(label, 0) + 1

        if included_animals_for_guest:
            included_guests += 1

    return {
        "guests": included_guests,
        "animals": included_animals,
        "species_counts": species_counts,
        "tag_counts": tag_counts,
    }


@food_bp.route("/food/plans", methods=["GET", "POST"])
@login_required
def plan_dispenses():
    can_edit = current_user.role in ("admin", "editor")
    try:
        tags_enabled = is_active("tagsystem")
    except ValueError:
        tags_enabled = False
    locations_enabled = is_active("locations")

    available_locations = (
        DropOffLocation.query.filter_by(is_dispense_location=True, active=True)
        .order_by(DropOffLocation.name.asc())
        .all()
        if locations_enabled
        else []
    )

    if request.method == "POST":
        if not can_edit:
            abort(403)
        plan_id = request.form.get("plan_id", type=int)
        plan = FoodDispensePlan.query.get(plan_id) if plan_id else None
        plan_date_val = (
            _parse_plan_date(request.form.get("plan_date"))
            or (plan.plan_date if plan else date.today())
        )
        location_id = request.form.get("location_id", type=int) if locations_enabled else None
        location_obj = (
            DropOffLocation.query.filter_by(
                id=location_id, is_dispense_location=True, active=True
            ).first()
            if location_id
            else None
        )
        if location_id and not location_obj:
            location_id = None

        guests, used_fallback = _load_planning_guests(location_id, locations_enabled)
        payload_guests = _build_plan_payload(
            guests, plan.payload if plan else None, tags_enabled
        )

        guest_ids = set(request.form.getlist("guest_ids"))
        animal_keys = set(request.form.getlist("animal_ids"))
        _apply_selection(payload_guests, guest_ids, animal_keys)

        payload = {
            "plan_date": plan_date_val.isoformat(),
            "location_id": location_id,
            "location_name": location_obj.name if location_obj else None,
            "guests": payload_guests,
        }
        summary = _compute_plan_summary(payload, tags_enabled)

        if plan:
            plan.plan_date = plan_date_val
            plan.location_id = location_id
            plan.payload = payload
            plan.summary = summary
        else:
            plan = FoodDispensePlan(
                plan_date=plan_date_val,
                location_id=location_id,
                payload=payload,
                summary=summary,
                created_by_id=current_user.id,
            )
            db.session.add(plan)

        db.session.commit()
        if used_fallback and locations_enabled and location_id:
            flash("Keine Gäste für diesen Standort gefunden. Es wurden alle aktiven Gäste aufgenommen.", "info")
        flash("Plan gespeichert.", "success")
        return redirect(url_for("food.plan_dispenses", plan_id=plan.id))

    plan_id = request.args.get("plan_id", type=int)
    selected_plan = FoodDispensePlan.query.get(plan_id) if plan_id else None
    if plan_id and not selected_plan:
        flash("Plan nicht gefunden.", "warning")
        return redirect(url_for("food.plan_dispenses"))

    plan_date_val = (
        selected_plan.plan_date
        if selected_plan
        else _parse_plan_date(request.args.get("plan_date")) or date.today()
    )
    location_id = (
        selected_plan.location_id
        if selected_plan
        else (request.args.get("location_id", type=int) if locations_enabled else None)
    )
    location_obj = DropOffLocation.query.get(location_id) if location_id else None
    if location_id and not location_obj:
        location_id = None

    guests, used_fallback = _load_planning_guests(location_id, locations_enabled)
    payload_guests = _build_plan_payload(
        guests, selected_plan.payload if selected_plan else None, tags_enabled
    )

    payload = dict(selected_plan.payload or {}) if selected_plan else {}
    fallback_location_name = payload.get("location_name") if payload else None
    payload.update(
        {
            "plan_date": plan_date_val.isoformat(),
            "location_id": location_id,
            "location_name": location_obj.name if location_obj else fallback_location_name,
            "guests": payload_guests,
        }
    )
    summary = _compute_plan_summary(payload, tags_enabled)

    plans = (
        FoodDispensePlan.query.order_by(
            FoodDispensePlan.plan_date.desc(), FoodDispensePlan.created_on.desc()
        )
        .limit(50)
        .all()
    )

    if used_fallback and locations_enabled and location_id:
        flash("Keine Gäste für diesen Standort gefunden. Es werden alle aktiven Gäste angezeigt.", "info")

    return render_template(
        "food_plan.html",
        title="Futterausgabe planen",
        payload=payload,
        summary=summary,
        available_locations=available_locations,
        locations_enabled=locations_enabled,
        tags_enabled=tags_enabled,
        plans=plans,
        selected_plan=selected_plan,
        can_edit=can_edit,
        used_location_fallback=used_fallback,
    )


@food_bp.route("/guest/<guest_id>/create_food_entry", methods=["POST"])
@login_required
def create_food_entry(guest_id):
    notiz = get_form_value("notiz")
    zahlungKommentar_futter = get_form_value("zahlungKommentar_futter")
    futter_betrag = request.form.get("futter_betrag", type=float, default=0.0)
    zubehoer_betrag = request.form.get("zubehoer_betrag", type=float, default=0.0)
    locations_enabled = is_active("locations")
    location_id = request.form.get("dispense_location_id", type=int) if locations_enabled else None

    today = datetime.now().date()
    guest = Guest.query.get(guest_id)

    resolved_location_id = None
    if locations_enabled and location_id:
        loc = DropOffLocation.query.filter_by(id=location_id, is_dispense_location=True).first()
        if loc and loc.active:
            resolved_location_id = loc.id

    new_entry = FoodHistory(
        guest_id=guest_id,
        distributed_on=today,
        comment=notiz,
        location_id=resolved_location_id,
    )
    db.session.add(new_entry)

    # Associate selected tags with this food history entry
    for form_key, tag_ids in request.form.lists():
        if form_key.startswith('tag_ids_'):
            for tag_id in tag_ids:
                tag = FoodTag.query.get(int(tag_id))
                if tag:
                    new_entry.distributed_tags.append(tag)

    
    if is_active("payments") and (futter_betrag > 0.0 or zubehoer_betrag > 0.0):
        save_payment_entry(guest_id, futter_betrag, zubehoer_betrag, zahlungKommentar_futter)
        flash("Futterverteilung und Zahlung gespeichert.", "success")
    else:
        flash("Futterverteilung gespeichert.", "success")

    db.session.commit()


    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@food_bp.route("/feed_entry/<int:entry_id>/edit", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def edit_feed_entry(entry_id):
    entry = FoodHistory.query.get(entry_id)
    if not entry:
        flash("Eintrag nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))

    if request.method == "POST":
        new_date = request.form.get("futtertermin")
        new_note = request.form.get("notiz", "")
        locations_enabled = is_active("locations")
        location_id = request.form.get("dispense_location_id", type=int) if locations_enabled else None
        entry.distributed_on = new_date
        entry.comment = new_note
        if locations_enabled:
            if location_id:
                loc = DropOffLocation.query.filter_by(id=location_id, is_dispense_location=True).first()
                entry.location_id = loc.id if loc else None
            else:
                entry.location_id = None
        db.session.commit()
        flash("Futtereintrag aktualisiert.", "success")
        return redirect(url_for("guest.view_guest", guest_id=entry.guest_id))
    return None


@food_bp.route("/feed_entry/<int:entry_id>/delete", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def delete_feed_entry(entry_id):
    entry = FoodHistory.query.get(entry_id)
    if not entry:
        flash("Eintrag nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))

    guest_id = entry.guest_id
    db.session.delete(entry)
    db.session.commit()
    flash("Futtereintrag gelöscht.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@food_bp.route("/food/plans/<int:plan_id>/report", methods=["GET"])
@login_required
def plan_report(plan_id):
    plan = FoodDispensePlan.query.get_or_404(plan_id)
    try:
        tags_enabled = is_active("tagsystem")
    except ValueError:
        tags_enabled = False
    payload = plan.payload or {}
    summary = plan.summary or _compute_plan_summary(payload, tags_enabled)
    return render_template(
        "reports/food_plan.html",
        plan=plan,
        payload=payload,
        summary=summary,
        tags_enabled=tags_enabled,
        now=datetime.now(),
        title="Paketliste",
    )
