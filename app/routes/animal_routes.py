from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from ..db import db_cursor
from ..helpers import add_changelog, roles_required, get_form_value

animal_bp = Blueprint("animal", __name__)


@animal_bp.route("/guest/<guest_id>/<int:animal_id>/edit", methods=["GET"])
@roles_required("admin", "editor")
@login_required
def edit_animal(guest_id, animal_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM gaeste WHERE id = %s", (guest_id,))
        gast = cursor.fetchone()
        if gast:
            cursor.execute(
                "SELECT * FROM tiere WHERE gast_id = %s AND id = %s",
                (gast["id"], animal_id),
            )
            tier = cursor.fetchone()
        else:
            flash("Gast nicht gefunden.", "danger")
            return redirect(url_for("guest.index"))

    if gast and tier:
        return render_template(
            "edit_animal.html", guest=gast, animal=tier, scanning_enabled=False
        )
    else:
        flash("Tier nicht gefunden.", "danger")
        return redirect(url_for("guest.index"))


@animal_bp.route("/guest/register/animal", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def register_animal():
    guest_id = request.args.get("guest_id") or request.form.get("guest_id")
    if not guest_id:
        flash("Fehler - Gast ID fehlt - bitte Administrator kontaktieren!", "danger")
        return redirect(url_for("guest.index"))
    with db_cursor() as cursor:
        if request.method == "POST":
            now = datetime.now()
            tierart = get_form_value("art")
            rasse = get_form_value("rasse")
            tier_name = get_form_value("tier_name")
            geschlecht = get_form_value("tier_geschlecht")
            farbe = get_form_value("farbe")
            kastriert = get_form_value("kastriert")
            identifikation = get_form_value("identifikation")
            geburtsdatum = get_form_value("tier_geburtsdatum")
            gewicht = get_form_value("gewicht_groesse")
            krankheiten = get_form_value("krankheiten")
            unvertraeglichkeiten = get_form_value("unvertraeglichkeiten")
            futter = get_form_value("futter")
            vollversorgung = get_form_value("vollversorgung")
            zuletzt_gesehen = get_form_value("zuletzt_gesehen")
            tierarzt = get_form_value("tierarzt")
            futtermengeneintrag = get_form_value("futtermengeneintrag")
            aktiv = get_form_value("aktiv")
            steuerbescheid_bis = get_form_value("steuerbescheid")
            tier_notiz = get_form_value("tier_notizen")

            cursor.execute(
                """
                INSERT INTO tiere
                    (gast_id, art, rasse, name, geschlecht, farbe, kastriert, identifikation, geburtsdatum,
                     gewicht_oder_groesse, krankheiten, unvertraeglichkeiten, futter, vollversorgung,
                     zuletzt_gesehen, tierarzt, futtermengeneintrag, notizen, active, steuerbescheid_bis, erstellt_am, aktualisiert_am)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    guest_id,
                    tierart,
                    rasse,
                    tier_name,
                    geschlecht,
                    farbe,
                    kastriert,
                    identifikation,
                    geburtsdatum,
                    gewicht,
                    krankheiten,
                    unvertraeglichkeiten,
                    futter,
                    vollversorgung,
                    zuletzt_gesehen,
                    tierarzt,
                    futtermengeneintrag,
                    tier_notiz,
                    aktiv,
                    steuerbescheid_bis,
                    now,
                    now,
                ),
            )
            add_changelog(
                guest_id,
                "create",
                f"Tier '{tier_name}' hinzugefügt",
                cursor=cursor,
            )
            return redirect(url_for("guest.view_guest", guest_id=guest_id))
        else:
            cursor.execute("SELECT vorname, nachname FROM gaeste WHERE id = %s", (guest_id,))
            result = cursor.fetchone()
            guest_name = " ".join((result["vorname"], result["nachname"])) if result else "Unbekannt"
            return render_template(
                "register_animal.html", guest_id=guest_id, guest_name=guest_name
            )


@animal_bp.route("/guest/<guest_id>/<int:animal_id>/update", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def update_animal(guest_id, animal_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM tiere WHERE id = %s", (animal_id,))
        old_animal = cursor.fetchone()
        if not old_animal:
            flash("Tier nicht gefunden.", "danger")
            return redirect(url_for("guest.view_guest", guest_id=guest_id))

        art = get_form_value("art")
        rasse = get_form_value("rasse")
        name = get_form_value("tier_name")
        geschlecht = get_form_value("tier_geschlecht")
        farbe = get_form_value("farbe")
        kastriert = get_form_value("kastriert")
        identifikation = get_form_value("identifikation")
        geburtsdatum = get_form_value("tier_geburtsdatum")
        gewicht_groesse = get_form_value("gewicht_groesse")
        krankheiten = get_form_value("krankheiten")
        unvertraeglichkeiten = get_form_value("unvertraeglichkeiten")
        futter = get_form_value("futter")
        vollversorgung = get_form_value("vollversorgung")
        zuletzt_gesehen = get_form_value("zuletzt_gesehen")
        tierarzt = get_form_value("tierarzt")
        futtermengeneintrag = get_form_value("futtermengeneintrag")
        notizen = get_form_value("tier_notizen")
        aktiv = get_form_value("aktiv")
        steuerbescheid_bis = get_form_value("steuerbescheid")
        now = datetime.now()

        def is_different(new_value, old_value):
            if new_value in (None, "") and old_value in (None, ""):
                return False
            return str(new_value) != str(old_value)

        changes = []
        if is_different(art, old_animal["art"]):
            changes.append("Art geändert")
        if is_different(rasse, old_animal["rasse"]):
            changes.append("Rasse geändert")
        if is_different(name, old_animal["name"]):
            changes.append("Name geändert")
        if is_different(geschlecht, old_animal["geschlecht"]):
            changes.append("Geschlecht geändert")
        if is_different(farbe, old_animal["farbe"]):
            changes.append("Farbe geändert")
        if is_different(kastriert, old_animal["kastriert"]):
            changes.append("Kastriert geändert")
        if is_different(identifikation, old_animal["identifikation"]):
            changes.append("Identifikation geändert")
        if is_different(geburtsdatum, old_animal["geburtsdatum"]):
            changes.append("Geburtsdatum geändert")
        if is_different(gewicht_groesse, old_animal["gewicht_oder_groesse"]):
            changes.append("Gewicht/Größe geändert")
        if is_different(krankheiten, old_animal["krankheiten"]):
            changes.append("Krankheiten geändert")
        if is_different(unvertraeglichkeiten, old_animal["unvertraeglichkeiten"]):
            changes.append("Unverträglichkeiten geändert")
        if is_different(futter, old_animal["futter"]):
            changes.append("Futter geändert")
        if is_different(vollversorgung, old_animal["vollversorgung"]):
            changes.append("Vollversorgung geändert")
        if is_different(zuletzt_gesehen, old_animal["zuletzt_gesehen"]):
            changes.append("Zuletzt gesehen geändert")
        if is_different(tierarzt, old_animal["tierarzt"]):
            changes.append("Tierarzt geändert")
        if is_different(futtermengeneintrag, old_animal["futtermengeneintrag"]):
            changes.append("Futtermengeneintrag geändert")
        if is_different(notizen, old_animal["notizen"]):
            changes.append("Notizen geändert")
        if is_different(steuerbescheid_bis, old_animal["steuerbescheid_bis"]):
            changes.append("Steurbescheid-bis geändert")
        if is_different(aktiv, old_animal["active"]):
            changes.append("Aktivstatus geändert")

        if not changes:
            flash("Keine Änderungen am Tier erkannt.", "info")
            return redirect(url_for("guest.view_guest", guest_id=guest_id))

        cursor.execute(
            """
            UPDATE tiere
            SET art = %s, rasse = %s, name = %s, geschlecht = %s, farbe = %s,
                kastriert = %s, identifikation = %s, geburtsdatum = %s, gewicht_oder_groesse = %s,
                krankheiten = %s, unvertraeglichkeiten = %s, futter = %s, vollversorgung = %s,
                zuletzt_gesehen = %s, tierarzt = %s, futtermengeneintrag = %s, notizen = %s,active = %s,steuerbescheid_bis = %s,
                aktualisiert_am = %s
            WHERE id = %s
            """,
            (
                art,
                rasse,
                name,
                geschlecht,
                farbe,
                kastriert,
                identifikation,
                geburtsdatum,
                gewicht_groesse,
                krankheiten,
                unvertraeglichkeiten,
                futter,
                vollversorgung,
                zuletzt_gesehen,
                tierarzt,
                futtermengeneintrag,
                notizen,
                aktiv,
                steuerbescheid_bis,
                now,
                animal_id,
            ),
        )

        add_changelog(
            guest_id,
            "update",
            f"Tier '{old_animal['name']}' bearbeitet: " + ", ".join(changes),
            cursor,
        )

        flash("Tierdaten erfolgreich aktualisiert.", "success")
        return redirect(url_for("guest.view_guest", guest_id=guest_id))


@animal_bp.route("/guest/<guest_id>/edit_animal_notes/<int:animal_id>", methods=["POST"])
@login_required
def edit_animal_notes(guest_id, animal_id):
    with db_cursor() as cursor:
        new_notes = request.form.get("notizen", "").strip()
        cursor.execute(
            "UPDATE tiere SET notizen = %s, aktualisiert_am = %s WHERE id = %s",
            (new_notes, datetime.now(), animal_id),
        )
    flash("Tiernotizen aktualisiert.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))


@animal_bp.route("/guest/<guest_id>/<int:animal_id>/delete", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def delete_animal(guest_id, animal_id):
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM tiere WHERE id = %s", (animal_id,))
    add_changelog(guest_id, "delete", f"Tier gelöscht (ID: {animal_id})", cursor)
    flash("Tier wurde gelöscht.", "success")
    return redirect(url_for("guest.view_guest", guest_id=guest_id))
