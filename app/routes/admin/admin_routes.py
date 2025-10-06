from collections import defaultdict
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app, send_file,
)
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from ...auth import get_user_by_username
from ...helpers import roles_required, get_form_value
from ...models import db, Guest, Animal, User, FoodHistory, Payment, FieldRegistry, Setting, FoodTag
from ...reports import generate_multiple_gast_cards_pdf, generate_payment_report

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/")
@login_required
@roles_required("admin")
def dashboard():
    from datetime import date, timedelta

    total_guests = Guest.query.count()
    active_guests = Guest.query.filter_by(status=1).count()

    last_30_days = date.today() - timedelta(days=30)
    recent_guests = (
        FoodHistory.query.filter(FoodHistory.distributed_on >= last_30_days)
        .with_entities(FoodHistory.guest_id)
        .distinct()
        .count()
    )

    total_animals = Animal.query.count()
    animals_by_type = (
        Animal.query.with_entities(Animal.species, db.func.count().label("count"))
        .group_by(Animal.species)
        .all()
    )

    top_guests_by_visits = (
        db.session.query(Guest.number, Guest.firstname, Guest.lastname, Guest.id,
                         db.func.count(FoodHistory.id).label("besuche"))
        .outerjoin(FoodHistory, Guest.id == FoodHistory.guest_id)
        .group_by(Guest.id)
        .order_by(db.desc("besuche"))
        .limit(10)
        .all()
    )

    payment_trends = (
        db.session.query(
            FoodHistory.distributed_on,
            db.func.coalesce(db.func.sum(Payment.food_amount), 0).label("Futtersumme"),
            db.func.coalesce(db.func.sum(Payment.other_amount), 0).label("Andere"),
        )
        .outerjoin(Payment,
                   (FoodHistory.guest_id == Payment.guest_id) & (Payment.paid_on == FoodHistory.distributed_on))
        .group_by(FoodHistory.distributed_on)
        .order_by(FoodHistory.distributed_on.asc())
        .limit(30)
        .all()
    )
    # Count animals per food tag using SQLAlchemy (ORM/Core hybrid)
    aft = db.metadata.tables.get('animal_food_tags')
    foodtag_counts = (
        db.session.query(
            FoodTag.id.label('id'),
            FoodTag.name.label('name'),
            db.func.count(aft.c.animal_id).label('count'),
        )
        .outerjoin(aft, aft.c.food_tag_id == FoodTag.id)
        .group_by(FoodTag.id, FoodTag.name)
        .order_by(FoodTag.name.asc())
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        current_user=current_user,
        total_guests=total_guests,
        active_guests=active_guests,
        recent_guests=recent_guests,
        total_animals=total_animals,
        animals_by_type=animals_by_type,
        top_guests_by_visits=top_guests_by_visits,
        payment_trends=payment_trends,
        foodtag_counts=foodtag_counts,
        title="Dashboard"
    )

@admin_bp.route("/list_users")
@roles_required("admin")
@login_required
def list_users():
    users = User.query.all()
    return render_template(
        "admin/list_users.html", users=users, title="Benutzerverwaltung"
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
@login_required
def edit_user(user_id):
    user = User.query.get(user_id)
    if not user:
        flash("Benutzer nicht gefunden.", "danger")
        return redirect(url_for("admin.list_users"))
    if request.method == "POST":
        username = get_form_value("username")
        role = get_form_value("role")
        new_password = get_form_value("password")
        realname = get_form_value("realname")
        user.username = username
        user.role = role
        user.realname = realname
        if new_password:
            user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Benutzer erfolgreich aktualisiert.", "success")
        return redirect(url_for("admin.list_users"))
    else:
        return render_template(
            "admin/edit_user.html", user=user, title="Benutzer bearbeiten"
        )


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@roles_required("admin")
@login_required
def delete_user(user_id):
    User.query.filter_by(id=user_id).delete()
    db.session.commit()
    flash("Benutzer erfolgreich gelöscht.", "success")
    return redirect(url_for("admin.list_users"))


@admin_bp.route("/field_visibility", methods=["POST"])
@roles_required("admin")
@login_required
def update_field_visibility():
    visible_ids = set(map(int, request.form.getlist("visible_fields")))
    all_fields = FieldRegistry.query.all()
    for field in all_fields:
        field.globally_visible = field.id in visible_ids
        new_level = get_form_value(f"visibility_level_{field.id}")
        if new_level != field.visibility_level:
            field.visibility_level = new_level
        new_level_e = get_form_value(f"editability_level_{field.id}")
        if new_level_e != field.editability_level:
            field.editability_level = new_level_e
        new_ui = get_form_value(f"ui_label_{field.id}")
        if new_ui != field.ui_label:
            field.ui_label = new_ui

        # Inline-Anzeige aktualisieren
        new_inline = f"show_inline_{field.id}" in request.form
        if new_inline != field.show_inline:
            field.show_inline = new_inline

        # Reihenfolge aktualisieren
        new_order = request.form.get(f"display_order_{field.id}")
        if new_order is not None:
            try:
                new_order_int = int(new_order)
                if new_order_int != field.display_order:
                    field.display_order = new_order_int
            except ValueError:
                pass
    db.session.commit()
    flash("Feldsichtbarkeit wurde aktualisiert.", "success")
    return redirect(url_for("admin.edit_settings", tab="foodtags"))


@admin_bp.route("/food_tags", methods=["POST"])
@roles_required("admin")
@login_required
def update_foodtags():
    # Update or delete existing tags
    existing_tags = FoodTag.query.all()
    for tag in existing_tags:
        # Delete if checkbox checked
        if request.form.get(f"delete_{tag.id}") == "1":
            db.session.delete(tag)
        else:
            # Update name if changed
            new_name = request.form.get(f"name_{tag.id}")
            if new_name and new_name != tag.name:
                tag.name = new_name
            # Update color if changed
            new_color = request.form.get(f"color_{tag.id}")
            if new_color and new_color != tag.color:
                tag.color = new_color

    # Create new tags from array inputs
    new_names = request.form.getlist("new_name[]")
    new_colors = request.form.getlist("new_color[]")
    for name, color in zip(new_names, new_colors):
        name = name.strip()
        if name:
            new_tag = FoodTag(name=name, color=color)
            db.session.add(new_tag)

    # Commit changes
    db.session.commit()
    flash("Foodtags wurden aktualisiert.", "success")
    return redirect(url_for("admin.edit_settings", tab="foodtags"))

@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_settings():
    if request.method == "POST":
        # Gehe alle Settings durch und update sie
        for key in request.form:
            value = get_form_value(key)
            setting = Setting.query.filter_by(setting_key=key).first()
            if setting:
                # Update existing setting
                setting.value = value if value else ''
            else:
                # Create a new setting if it doesn’t exist
                new_setting = Setting(setting_key=key, value=value)
                db.session.add(new_setting)
        # Commit all changes at once
        db.session.commit()

        current_app.refresh_settings()

        flash("Einstellungen wurden gespeichert und aktualisiert.", "success")
        return redirect(url_for("admin.edit_settings"))
    else:
        # GET: zeige aktuelle Settings
        # group optional fields by model
        field_registry = defaultdict(list)
        query = FieldRegistry.query.order_by(FieldRegistry.model_name, FieldRegistry.field_name).all()
        for field in query:
            field_registry[field.model_name].append(field)

        tags = FoodTag.query.all()

        settings = Setting.query.all()
        settings = {item["setting_key"]: item for item in settings}
        return render_template("admin/edit_settings.html", settings=settings, field_registry=field_registry,
                               foodtags=tags)


@admin_bp.route("/users/register", methods=["GET", "POST"])
@roles_required("admin")
@login_required
def register_user():
    if request.method == "POST":
        username = get_form_value("username")
        password = get_form_value("password")
        role = get_form_value("role")
        realname = get_form_value("realname")
        if not username or not password or not role:
            flash("Bitte alle Felder ausfüllen.", "danger")
            return redirect(url_for("auth.create_user"))
        if get_user_by_username(username):
            flash("Benutzername existiert bereits.", "danger")
            return redirect(url_for("auth.create_user"))
        password_hash = generate_password_hash(password)
        user = User(username=username, password_hash=password_hash, role=role, realname=realname)
        db.session.add(user)
        db.session.commit()
        flash("Benutzer erfolgreich angelegt.", "success")
        return redirect(url_for("admin.list_users"))
    return render_template("admin/register_user.html", title="Benutzer anlegen")





@admin_bp.route("/export_transactions", methods=["GET"])
@roles_required("admin")
@login_required
def export_transactions():
    from datetime import datetime

    from_date = request.args.get("from")
    to_date = request.args.get("to")

    if not from_date or not to_date:
        flash("Bitte gib ein gültiges Start- und Enddatum an.", "danger")
        return redirect(url_for("admin.dashboard"))

    try:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d").date()
        to_dt = datetime.strptime(to_date, "%Y-%m-%d").date()
    except ValueError:
        flash("Ungültiges Datumsformat.", "danger")
        return redirect(url_for("admin.dashboard"))

    # Load transactions via SQLAlchemy
    records = (
        db.session.query(
            Payment.paid_on,
            Guest.number,
            Guest.firstname,
            Guest.lastname,
            Payment.food_amount,
            Payment.other_amount,
            Payment.comment
        )
        .join(Guest, Payment.guest_id == Guest.id)
        .filter(Payment.paid_on.between(from_dt, to_dt))
        .order_by(Payment.paid_on.asc())
        .all()
    )
    # Compute totals
    total_food = sum(r.food_amount for r in records)
    total_other = sum(r.other_amount for r in records)

    return render_template(
        "reports/transaction_report.html",
        transactions=records,
        current_user=current_user,
        from_date=from_dt.strftime('%d.%m.%Y'),
        to_date=to_dt.strftime('%d.%m.%Y'),
        total_food=total_food,
        total_other=total_other,
        now = datetime.today(),
        title="Zahlungsbericht"
    )

@admin_bp.route("/print_export_transactions", methods=["GET", "POST"])
@roles_required("admin")
@login_required
def print_export_transactions():
    # Read date range from query parameters
    from_date_str = request.args.get('from_date')
    to_date_str = request.args.get('to_date')
    try:
        from_dt = datetime.strptime(from_date_str, '%d.%m.%Y').date()
        to_dt = datetime.strptime(to_date_str, '%d.%m.%Y').date()
    except (TypeError, ValueError):
        flash("Ungültiges Datumsformat.", "danger")
        return redirect(url_for('admin.export_transactions'))
    # Load transactions via SQLAlchemy
    records = (
        db.session.query(
            Payment.paid_on,
            Guest.number,
            Guest.firstname,
            Guest.lastname,
            Payment.food_amount,
            Payment.other_amount,
            Payment.comment
        )
        .join(Guest, Payment.guest_id == Guest.id)
        .filter(Payment.paid_on.between(from_dt, to_dt))
        .order_by(Payment.paid_on.asc())
        .all()
    )
    # Generate PDF
    pdf_buffer = generate_payment_report(records, from_dt, to_dt)
    filename = f"zahlungsexport_{from_dt.isoformat()}_bis_{to_dt.isoformat()}.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )


# Neue Route: Gästekarten-Ansicht für Admin
@admin_bp.route("/guest_cards", methods=["GET"])
@login_required
@roles_required("admin")
def guest_cards():
    """
    Admin-View: Liste aller Gäste zum Auswählen für die Gästekarten-Erstellung.
    """
    # Alle Gäste abrufen
    guests = Guest.query.all()
    return (render_template(
        "admin/print_guest_cards.html",
        guests=guests,
        title="Gästekarten erstellen"
    ))




@admin_bp.route("/print_guest_cards", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def print_guest_cards():
    # IDs der ausgewählten Gäste aus dem Formular holen
    guest_ids = request.form.getlist('guest_ids')
    guest_ids = list(set(guest_ids))
    if guest_ids:
        if request.form.get("backside"):
            pdf_bytes = generate_multiple_gast_cards_pdf(guest_ids, double_sided=True)
        else:
            pdf_bytes = generate_multiple_gast_cards_pdf(guest_ids)
        Guest.query \
            .filter(Guest.id.in_(guest_ids)) \
            .update({"guest_card_printed_on": datetime.today()}, synchronize_session=False)
        db.session.commit()
        return send_file(
            pdf_bytes,
            as_attachment=True,
            download_name=f"Karten-{datetime.today()}.pdf",
            mimetype="application/pdf",
        )
    return redirect(url_for("admin.guest_cards"))
