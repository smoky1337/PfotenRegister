from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_login import login_required

from ..db import db_cursor
from ..models import db as sqlalchemy_db, Guest, Animal
from ..helpers import (
    generate_unique_code,
    get_food_history,
    add_changelog,
    roles_required,
    get_form_value,
    generate_guest_number,
)
from ..pdf import generate_gast_card_pdf

guest_bp = Blueprint("guest", __name__)


@guest_bp.route("/")
@login_required
def index():
    guests = session.get("guest_cache")
    if guests is None or session.get("guests_changed", False):
        rows = Guest.query.order_by(Guest.nachname).with_entities(
            Guest.id, Guest.vorname, Guest.nachname
        ).all()
        guests = [{"id": r.id, "name": f"{r.vorname} {r.nachname}"} for r in rows]
        session["guest_cache"] = guests
        session["guests_changed"] = False
    return render_template("start.html", guests=guests)


@guest_bp.route("/guest/search")
@login_required
def search_guests():
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return jsonify([])

    results = (
        Guest.query.filter(
            (Guest.vorname.ilike(f"%{query}%")) | (Guest.nachname.ilike(f"%{query}%"))
        )
        .order_by(Guest.nachname)
        .limit(10)
        .all()
    )

    return jsonify([
        {"id": g.id, "name": f"{g.vorname} {g.nachname}"} for g in results
    ])


@guest_bp.route("/guest/<guest_id>")
@login_required
def view_guest(guest_id):
    gast = Guest.query.get(guest_id)
    if gast:
        animals = Animal.query.filter_by(gast_id=gast.id).all()
        feed_history = get_food_history(gast.id)
        with db_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM changelog WHERE gast_id = %s ORDER BY change_timestamp DESC LIMIT 10",
                (gast.id,),
            )
            changelog = cursor.fetchall()
            cursor.execute(
                "SELECT * FROM zahlungshistorie WHERE gast_id = %s ORDER BY zahlungstag DESC LIMIT 10",
                (gast.id,),
            )
            payments = cursor.fetchall()
    else:
        animals = []
        changelog = []
        feed_history = []
        payments = []
    if gast:
        return render_template(
            "view_guest.html",
            guest=gast,
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
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM gaeste WHERE id = %s", (guest_id,))
        gast = cursor.fetchone()
        if gast:
            cursor.execute("SELECT * FROM tiere WHERE gast_id = %s", (gast["id"],))
            animals = cursor.fetchall()
            feed_history = get_food_history(gast["id"])
            prev_ids = [t["id"] for t in animals]
        else:
            animals = []
            feed_history = []
            prev_ids = []

    if gast:
        return render_template(
            "edit_guest.html",
            guest=gast,
            animals=animals,
            feed_history=feed_history,
            prev_ids=prev_ids,
            scanning_enabled=False,
        )
    else:
        flash("Gast nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))


@guest_bp.route("/guest/list")
@login_required
def list_guests():
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM gaeste")
        guests = cursor.fetchall()
        guest_ids = [g["id"] for g in guests]
        feed_history = {}
        if guest_ids:
            placeholders = ", ".join(["%s"] * len(guest_ids))
            query2 = f"""
                   SELECT gast_id, MAX(futtertermin) AS latest
                   FROM futterhistorie
                   WHERE gast_id IN ({placeholders})
                   GROUP BY gast_id
               """
            cursor.execute(query2, tuple(guest_ids))
            rows = cursor.fetchall()
            for row in rows:
                feed_history[row["gast_id"]] = row["latest"]

    active_guests = []
    inactive_guests = []

    for g in guests:
        if g["status"] == "Aktiv":
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
            vorname = get_form_value("vorname")
            nachname = get_form_value("nachname")
            adresse = get_form_value("adresse")
            plz = get_form_value("plz")
            ort = get_form_value("ort")
            festnetz = get_form_value("festnetz")
            mobil = get_form_value("mobil")
            email = get_form_value("email")
            geburtsdatum = get_form_value("geburtsdatum")
            geschlecht = get_form_value("geschlecht")
            eintritt = get_form_value("eintritt")
            austritt = get_form_value("austritt")
            status = get_form_value("status").strip()
            beduerftigkeit = get_form_value("beduerftigkeit")
            beduerftig_bis = get_form_value("beduerftig_bis")
            dokumente = get_form_value("dokumente")
            notizen = get_form_value("notizen")

            vertreter_name = get_form_value("vertreter_name")
            vertreter_telefon = get_form_value("vertreter_telefon")
            vertreter_email = get_form_value("vertreter_email")
            vertreter_adresse = get_form_value("vertreter_adresse")
            if (
                not vorname
                or not nachname
                or not adresse
                or not plz
                or not ort
                or not geburtsdatum
                or not eintritt
                or not beduerftigkeit
            ):
                flash(
                    "Bitte füllen Sie alle Pflichtfelder aus: Vorname, Nachname, Adresse, PLZ, Ort, Geburtsdatum, Eintritt und Bedürftigkeit.",
                    "danger",
                )
                return redirect(url_for("guest.register_guest"))

            if not (festnetz or mobil or email):
                flash(
                    "Bitte geben Sie mindestens eine Kontaktmöglichkeit an (Festnetz, Mobil oder E-Mail).",
                    "danger",
                )
                return redirect(url_for("guest.register_guest"))

            existing = Guest.query.filter_by(
                vorname=vorname,
                nachname=nachname,
                adresse=adresse,
                plz=plz,
                ort=ort,
            ).first()
            if existing:
                flash(
                    "Ein Gast mit diesem Namen und dieser Anschrift existiert bereits.",
                    "danger",
                )
                return redirect(url_for("guest.register_guest"))

            guest_id = generate_unique_code(length=6)
            now = datetime.now()

            nummer = generate_guest_number()
            guest = Guest(
                id=guest_id,
                nummer=nummer,
                vorname=vorname,
                nachname=nachname,
                adresse=adresse,
                plz=plz,
                ort=ort,
                festnetz=festnetz,
                mobil=mobil,
                email=email,
                geburtsdatum=geburtsdatum if geburtsdatum else None,
                geschlecht=geschlecht if geschlecht else None,
                eintritt=eintritt,
                austritt=austritt if austritt else None,
                vertreter_name=vertreter_name if vertreter_name else None,
                vertreter_telefon=vertreter_telefon if vertreter_telefon else None,
                vertreter_email=vertreter_email if vertreter_email else None,
                vertreter_adresse=vertreter_adresse if vertreter_adresse else None,
                status=status,
                beduerftigkeit=beduerftigkeit if beduerftigkeit else None,
                beduerftig_bis=beduerftig_bis if beduerftig_bis else None,
                dokumente=dokumente if dokumente else None,
                notizen=notizen if notizen else None,
                erstellt_am=now,
                aktualisiert_am=now,
            )
            sqlalchemy_db.session.add(guest)
            sqlalchemy_db.session.commit()

            add_changelog(guest_id, "create", "Gast erstellt")
            session["guests_changed"] = True

            action = request.form.get("action", "next")
            if action == "finish":
                flash("Gast wurde gespeichert.", "success")
                return redirect(url_for("guest.view_guest", guest_id=guest_id))
            return redirect(url_for("animal.register_animal", guest_id=guest_id))
        else:
            return render_template(
                "register_guest.html",
                title="Gast Registrierung",
            )


@guest_bp.route("/guest/<guest_id>/update", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def update_guest(guest_id):
    with db_cursor() as cursor:
        vorname = get_form_value("vorname")
        nachname = get_form_value("nachname")
        nummer = get_form_value("nummer")
        adresse = get_form_value("adresse")
        plz = get_form_value("plz")
        ort = get_form_value("ort")
        festnetz = get_form_value("festnetz")
        mobil = get_form_value("mobil")
        email = get_form_value("email")
        geburtsdatum = get_form_value("geburtsdatum")
        geschlecht = get_form_value("geschlecht")
        austritt = get_form_value("austritt")
        status = get_form_value("status")
        beduerftigkeit = get_form_value("beduerftigkeit")
        beduerftig_bis = get_form_value("beduerftig_bis")
        dokumente = get_form_value("dokumente")
        notizen = get_form_value("notizen")

        vertreter_name = get_form_value("vertreter_name")
        vertreter_telefon = get_form_value("vertreter_telefon")
        vertreter_email = get_form_value("vertreter_email")
        vertreter_adresse = get_form_value("vertreter_adresse")

        cursor.execute("SELECT * FROM gaeste WHERE id = %s", (guest_id,))
        gast_alt = cursor.fetchone()

        changes = []

        def is_different(new_value, old_value):
            if new_value in (None, "") and old_value in (None, ""):
                return False
            return str(new_value) != str(old_value)

        if is_different(nummer, gast_alt["nummer"]):
            changes.append("Gastnummer geändert")
        if is_different(vorname, gast_alt["vorname"]):
            changes.append("Vorname geändert")
        if is_different(nachname, gast_alt["nachname"]):
            changes.append("Nachname geändert")
        if is_different(adresse, gast_alt["adresse"]):
            changes.append("Adresse geändert")
        if is_different(plz, gast_alt["plz"]):
            changes.append("PLZ geändert")
        if is_different(ort, gast_alt["ort"]):
            changes.append("Ort geändert")
        if is_different(festnetz, gast_alt["festnetz"]):
            changes.append("Festnetz geändert")
        if is_different(mobil, gast_alt["mobil"]):
            changes.append("Mobil geändert")
        if is_different(email, gast_alt["email"]):
            changes.append("E-Mail geändert")
        if is_different(geburtsdatum, gast_alt["geburtsdatum"]):
            changes.append("Geburtsdatum geändert")
        if is_different(geschlecht, gast_alt["geschlecht"]):
            changes.append("Geschlecht geändert")
        if is_different(austritt, gast_alt["austritt"]):
            changes.append("Austritt geändert")
        if is_different(status, gast_alt["status"]):
            changes.append("Status geändert")
        if is_different(beduerftigkeit, gast_alt["beduerftigkeit"]):
            changes.append("Bedürftigkeit geändert")
        if is_different(beduerftig_bis, gast_alt["beduerftig_bis"]):
            changes.append("Bedürftig bis geändert")
        if is_different(dokumente, gast_alt["dokumente"]):
            changes.append("Dokumente geändert")
        if is_different(notizen, gast_alt["notizen"]):
            changes.append("Notizen geändert")
        if is_different(vertreter_name, gast_alt["vertreter_name"]):
            changes.append("Vertretername geändert")
        if is_different(vertreter_telefon, gast_alt["vertreter_telefon"]):
            changes.append("Vertretertelefon geändert")
        if is_different(vertreter_email, gast_alt["vertreter_email"]):
            changes.append("Vertreter-E-Mail geändert")
        if is_different(vertreter_adresse, gast_alt["vertreter_adresse"]):
            changes.append("Vertreteradresse geändert")

        if not changes:
            flash("Keine Änderungen erkannt.", "info")
            return redirect(url_for("guest.view_guest", guest_id=guest_id))

        session["guests_changed"] = True
        cursor.execute(
            """
            UPDATE gaeste
            SET nummer = %s,
                vorname = %s,
                nachname = %s,
                adresse = %s,
                plz = %s,
                ort = %s,
                festnetz = %s,
                mobil = %s,
                email = %s,
                geburtsdatum = %s,
                geschlecht = %s,
                austritt = %s,
                status = %s,
                beduerftigkeit = %s,
                beduerftig_bis = %s,
                dokumente = %s,
                notizen = %s,
                aktualisiert_am = %s,
                vertreter_name = %s,
                vertreter_telefon = %s,
                vertreter_email = %s,
                vertreter_adresse = %s
            WHERE id = %s
        """,
            (
                nummer,
                vorname,
                nachname,
                adresse,
                plz,
                ort,
                festnetz,
                mobil,
                email,
                geburtsdatum if geburtsdatum else None,
                geschlecht if geschlecht else None,
                austritt if austritt else None,
                status,
                beduerftigkeit if beduerftigkeit else None,
                beduerftig_bis if beduerftig_bis else None,
                dokumente if dokumente else None,
                notizen if notizen else None,
                datetime.now(),
                vertreter_name if vertreter_name else None,
                vertreter_telefon if vertreter_telefon else None,
                vertreter_email if vertreter_email else None,
                vertreter_adresse if vertreter_adresse else None,
                guest_id,
            ),
        )

        add_changelog(
            guest_id,
            "update",
            "Folgende Felder geändert: " + ", ".join(changes),
            cursor,
        )
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
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM gaeste WHERE id = %s", (guest_id,))
        gast = cursor.fetchone()
    if gast:
        pdf_bytes = generate_gast_card_pdf("".join((gast["vorname"], gast["nachname"])), gast["id"])
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
    with db_cursor() as cursor:
        new_notes = request.form.get("notizen", "").strip()
        cursor.execute(
            "UPDATE gaeste SET notizen = %s, aktualisiert_am = %s WHERE id = %s",
            (new_notes, datetime.now(), guest_id),
        )
    flash("Notizen aktualisiert.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@guest_bp.route("/guest/<guest_id>/deactivate", methods=["POST"])
@roles_required("admin")
@login_required
def deactivate_guest(guest_id):
    with db_cursor() as cursor:
        cursor.execute(
            "UPDATE gaeste SET status = 'Inaktiv', aktualisiert_am = %s WHERE id = %s",
            (datetime.now(), guest_id),
        )
    add_changelog(guest_id, "update", "Gast deaktiviert")
    flash("Gast wurde deaktiviert.", "success")
    return redirect(url_for("guest.list_guests"))


@guest_bp.route("/guest/<guest_id>/activate", methods=["POST"])
@roles_required("admin")
@login_required
def activate_guest(guest_id):
    with db_cursor() as cursor:
        cursor.execute(
            "UPDATE gaeste SET status = 'Aktiv', aktualisiert_am = %s WHERE id = %s",
            (datetime.now(), guest_id),
        )
    add_changelog(guest_id, "update", "Gast aktiviert")
    flash("Gast wurde aktiviert.", "success")
    return redirect(url_for("guest.list_guests"))


@guest_bp.route("/guest/<guest_id>/delete", methods=["POST"])
@roles_required("admin")
@login_required
def delete_guest(guest_id):
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM tiere WHERE gast_id = %s", (guest_id,))
        cursor.execute("DELETE FROM futterhistorie WHERE gast_id = %s", (guest_id,))
        cursor.execute("DELETE FROM changelog WHERE gast_id = %s", (guest_id,))
        cursor.execute("DELETE FROM gaeste WHERE id = %s", (guest_id,))
    session["guests_changed"] = True
    flash("Gast wurde vollständig gelöscht.", "success")
    return redirect(url_for("guest.list_guests"))
