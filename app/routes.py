from datetime import datetime, timedelta

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    jsonify,
    session,
)
from flask_login import login_required

from .db import db_cursor
from .helpers import (
    generate_unique_code,
    get_food_history,
    add_changelog,
    roles_required,
    get_form_value,
)
from .pdf import generate_gast_card_pdf

bp = Blueprint("main", __name__)

###
# Template rendering
###


@bp.route("/")
@login_required
def index():
    guests = session.get("guest_cache")
    if guests is None or session.get("guests_changed", False):
        with db_cursor() as cursor:
            cursor.execute("SELECT id, vorname, nachname FROM gaeste ORDER BY nachname ASC")
            rows = cursor.fetchall()
        guests = [{"id": r["id"], "name": f"{r['vorname']} {r['nachname']}"} for r in rows]
        session["guest_cache"] = guests
        session["guests_changed"] = False
    return render_template("start.html", guests=guests)


# Live search for guests by name
@bp.route("/guest/search")
@login_required
def search_guests():
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return jsonify([])

    with db_cursor() as cursor:
        cursor.execute("""
            SELECT id, vorname, nachname 
            FROM gaeste 
            WHERE vorname ILIKE %s OR nachname ILIKE %s 
            ORDER BY nachname ASC LIMIT 10
        """, (f"%{query}%", f"%{query}%"))
        results = cursor.fetchall()

    return jsonify([{"id": g["id"], "name": f"{g['vorname']} {g['nachname']}"} for g in results])


@bp.route("/guest/<guest_id>")
@login_required
def view_guest(guest_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM gaeste WHERE id = %s", (guest_id,))
        gast = cursor.fetchone()
        if gast:
            cursor.execute("SELECT * FROM tiere WHERE gast_id = %s", (gast["id"],))
            animals = cursor.fetchall()
            feed_history = get_food_history(gast["id"])
            cursor.execute(
                "SELECT * FROM changelog WHERE gast_id = %s ORDER BY change_timestamp DESC LIMIT 10",
                (gast["id"],),
            )
            changelog = cursor.fetchall()
            cursor.execute("SELECT * FROM zahlungshistorie WHERE gast_id = %s ORDER BY zahlungstag DESC LIMIT 10", (gast["id"],))
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
            timedelta = timedelta
        )
    else:
        flash("Gast nicht gefunden.", "danger")
        return redirect(url_for("main.index"))



@bp.route("/guest/<guest_id>/<int:animal_id>/edit", methods=["GET"])
@roles_required("admin", "editor")
@login_required
def edit_animal(guest_id, animal_id):
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM gaeste WHERE id = %s", (guest_id,))
        gast = cursor.fetchone()

        if gast:
            # Retrieve the animal for the guest using the foreign key (guest_id)
            cursor.execute(
                "SELECT * FROM tiere WHERE gast_id = %s AND id = %s",
                (gast["id"], animal_id),
            )
            tier = cursor.fetchone()
        else:
            flash("Gast nicht gefunden.", "danger")
            return redirect(url_for("main.index"))

    if gast and tier:
        return render_template(
            "edit_animal.html", guest=gast, animal=tier, scanning_enabled=False
        )
    else:
        flash("Tier nicht gefunden.", "danger")
        return redirect(url_for("main.index"))


@bp.route("/guest/<guest_id>/edit", methods=["GET"])
@roles_required("admin", "editor")
@login_required
def edit_guest(guest_id):
    with db_cursor() as cursor:

        cursor.execute("SELECT * FROM gaeste WHERE id = %s", (guest_id,))
        gast = cursor.fetchone()
        if gast:
            # Retrieve all animals for the guest using the foreign key (guest_id)
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
        return redirect(url_for("main.index"))


@bp.route("/guest/list")
@login_required
def list_guests():
    with db_cursor() as cursor:

        cursor.execute("SELECT * FROM gaeste")
        guests = cursor.fetchall()

        # Build list of guest IDs from gaeste
        guest_ids = [g["id"] for g in guests]
        feed_history = {}
        if guest_ids:
            # Create a comma-separated list of placeholders
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


###
# Guest and animal registration
###


@bp.route("/guest/register", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def register_guest():
    with db_cursor() as cursor:

        if request.method == "POST":
            # Process guest data only
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

            # Retrieve legal guardian fields from the form
            vertreter_name = get_form_value("vertreter_name")
            vertreter_telefon = get_form_value("vertreter_telefon")
            vertreter_email = get_form_value("vertreter_email")
            vertreter_adresse = get_form_value("vertreter_adresse")
            # Pflichtfelder prüfen
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
                return redirect(url_for("main.register_guest"))

            # Prüfe auf mindestens eine Kontaktmöglichkeit
            if not (festnetz or mobil or email):
                flash(
                    "Bitte geben Sie mindestens eine Kontaktmöglichkeit an (Festnetz, Mobil oder E-Mail).",
                    "danger",
                )
                return redirect(url_for("main.register_guest"))

            # Prüfe auf Duplikate
            cursor.execute(
                "SELECT * FROM gaeste WHERE vorname = %s AND nachname = %s AND adresse = %s AND plz = %s AND ort = %s ",
                (vorname, nachname, adresse, plz, ort),
            )
            if cursor.fetchone():
                flash(
                    "Ein Gast mit diesem Namen und dieser Anschrift existiert bereits.",
                    "danger",
                )
                return redirect(url_for("main.register_guest"))

            # Erstelle einen eindeutigen guest_id und erhalte das aktuelle Datum
            guest_id = generate_unique_code(length=6)
            now = datetime.now()

            # Calculate auto-incremented guest number
            cursor.execute(
                "SELECT MAX(nummer) AS max_nummer FROM gaeste WHERE nummer LIKE 'GTT%'"
            )
            result = cursor.fetchone()
            if result and result["max_nummer"]:
                max_num = int(
                    result["max_nummer"][3:]
                )  # Extract numeric part from e.g. "GTT01"
                new_num = max_num + 1
            else:
                new_num = 1
            nummer = "GTT" + str(new_num)  # Formats as GTT....
            # Füge den neuen Gast ein
            cursor.execute(
                """
                INSERT INTO gaeste 
                  (nummer, vorname,nachname, adresse, plz, ort, festnetz, mobil, email, geburtsdatum, geschlecht, eintritt, austritt,
                   vertreter_name, vertreter_telefon, vertreter_email, vertreter_adresse, status, beduerftigkeit, beduerftig_bis, dokumente,
                   notizen, id, erstellt_am, aktualisiert_am)
                VALUES 
                  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    nummer,
                    vorname, nachname,
                    adresse, plz, ort,
                    festnetz,
                    mobil,
                    email,
                    geburtsdatum if geburtsdatum else None,
                    geschlecht if geschlecht else None,
                    eintritt,
                    austritt if austritt else None,
                    vertreter_name if vertreter_name else None,
                    vertreter_telefon if vertreter_telefon else None,
                    vertreter_email if vertreter_email else None,
                    vertreter_adresse if vertreter_adresse else None,
                    status,
                    beduerftigkeit if beduerftigkeit else None,
                    beduerftig_bis if beduerftig_bis else None,
                    dokumente if dokumente else None,
                    notizen if notizen else None,
                    guest_id,
                    now,
                    now,
                ),
            )

            # Optional: add changelog entry here
            add_changelog(guest_id, "create", "Gast erstellt", cursor=cursor)

            # Mark guest list as changed in session
            session["guests_changed"] = True

            # Redirect based on action
            action = request.form.get("action", "next")
            if action == "finish":
                flash("Gast wurde gespeichert.", "success")
                return redirect(url_for("main.view_guest", guest_id=guest_id))
            return redirect(url_for("main.register_animal", guest_id=guest_id))
        else:
            return render_template(
                "register_guest.html",
                title="Gast Registrierung",
            )


@bp.route("/guest/register/animal", methods=["GET", "POST"])
@roles_required("admin", "editor")
@login_required
def register_animal():

    # guest_id can be passed as a query parameter (GET) or hidden field (POST)
    guest_id = request.args.get("guest_id") or request.form.get("guest_id")
    if not guest_id:
        flash("Fehler - Gast ID fehlt - bitte Administrator kontaktieren!", "danger")
        return redirect(url_for("main.index"))
    with db_cursor() as cursor:
        if request.method == "POST":

            now = datetime.now()

            # Retrieve animal data from form
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
            return redirect(url_for("main.view_guest", guest_id=guest_id))
        else:
            # GET: Retrieve guest name and render the animal registration form
            cursor.execute("SELECT vorname, nachname FROM gaeste WHERE id = %s", (guest_id,))
            result = cursor.fetchone()
            guest_name = "".join((result["vorname"], result["nachname"])) if result else "Unbekannt"
            return render_template(
                "register_animal.html", guest_id=guest_id, guest_name=guest_name
            )


###
# Guest and animal general updating
###


@bp.route("/guest/<guest_id>/update", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def update_guest(guest_id):
    with db_cursor() as cursor:

        # Retrieve all guest fields from the form
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

        # Retrieve legal guardian fields from the form
        vertreter_name = get_form_value("vertreter_name")
        vertreter_telefon = get_form_value("vertreter_telefon")
        vertreter_email = get_form_value("vertreter_email")
        vertreter_adresse = get_form_value("vertreter_adresse")

        cursor.execute("SELECT * FROM gaeste WHERE id = %s", (guest_id,))
        gast_alt = cursor.fetchone()

        # Check if any actual changes are detected
        changes = []

        def is_different(new_value, old_value):
            # Leere Strings und None sollen als gleich gelten
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
            return redirect(url_for("main.view_guest", guest_id=guest_id))

        # Nur wenn Änderungen existieren, aktualisiere die Datenbank:
        # Mark guest list as changed in session
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

        # Und danach ins Änderungsprotokoll schreiben:
        add_changelog(
            guest_id,
            "update",
            "Folgende Felder geändert: " + ", ".join(changes),
            cursor,
        )
        flash("Gastdaten erfolgreich aktualisiert.", "success")
        return redirect(url_for("main.view_guest", guest_id=guest_id))


@bp.route("/guest/<guest_id>/<int:animal_id>/update", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def update_animal(guest_id, animal_id):
    with db_cursor() as cursor:
        # Retrieve old animal from database
        cursor.execute("SELECT * FROM tiere WHERE id = %s", (animal_id,))
        old_animal = cursor.fetchone()
        if not old_animal:
            flash("Tier nicht gefunden.", "danger")
            return redirect(url_for("main.view_guest", guest_id=guest_id))

        # Retrieve values from form
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

        # Helper to check if a value has changed
        def is_different(new_value, old_value):
            if new_value in (None, "") and old_value in (None, ""):
                return False
            return str(new_value) != str(old_value)

        # Detect changes
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
            return redirect(url_for("main.view_guest", guest_id=guest_id))

        # Perform update if needed
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

        # Log change
        add_changelog(
            guest_id,
            "update",
            f"Tier '{old_animal['name']}' bearbeitet: " + ", ".join(changes),
            cursor,
        )

        flash("Tierdaten erfolgreich aktualisiert.", "success")
        return redirect(url_for("main.view_guest", guest_id=guest_id))


###
# Guest logic
###


@bp.route("/guest/lookup")
@login_required
def guest_lookup():
    code = request.args.get("code", "").strip()
    if code:
        return redirect(url_for("main.view_guest", guest_id=code))
    else:
        flash("Bitte einen Barcode eingeben.", "danger")
        return redirect(url_for("main.index"))


@bp.route("/guest/<guest_id>/food_dispensed", methods=["POST"])
@login_required
def food_dispensed(guest_id):
    notiz = get_form_value("comment")
    zahlungKommentar_futter = get_form_value("zahlungKommentar_futter")
    futter_betrag = request.form.get("futter_betrag", type=float, default=0.0)
    zubehoer_betrag = request.form.get("zubehoer_betrag", type=float, default=0.0)
    with db_cursor() as cursor:
        today = datetime.now().date()
        cursor.execute(
            "INSERT INTO futterhistorie (gast_id, futtertermin, notiz) VALUES (%s, %s, %s)",
            (guest_id, today, notiz),
        )
        if futter_betrag > 0.0 or zubehoer_betrag > 0.0:
            cursor.execute("""
                INSERT INTO zahlungshistorie (gast_id, zahlungstag, futter_betrag, zubehoer_betrag, kommentar)
                VALUES (%s, %s, %s, %s, %s)
            """, (guest_id, today, futter_betrag, zubehoer_betrag, zahlungKommentar_futter))


    if futter_betrag > 0.0 or zubehoer_betrag > 0.0:
        flash("Futterverteilung und Zahlung gespeichert.", "success")
    else:
        flash("Futterverteilung gespeichert.", "success")

    return redirect(url_for("main.view_guest", guest_id=guest_id))


@bp.route("/guest/<guest_id>/print_card")
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
        return redirect(url_for("main.index"))


###
# Payment
###

@bp.route("/guest/<guest_id>/payment_direct", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def payment_guest_direct(guest_id):
    futter_betrag = request.form.get("futter_betrag", type=float, default=0.0)
    zubehoer_betrag = request.form.get("zubehoer_betrag", type=float, default=0.0)
    kommentar = get_form_value("kommentar")
    today = datetime.now().date()

    with db_cursor() as cursor:
        cursor.execute("""
            INSERT INTO zahlungshistorie (gast_id, zahlungstag, futter_betrag, zubehoer_betrag, kommentar)
            VALUES (%s, %s, %s, %s, %s)
        """, (guest_id, today, futter_betrag, zubehoer_betrag, kommentar))

    flash("Zahlung erfolgreich erfasst.", "success")
    return redirect(url_for("main.view_guest", guest_id=guest_id))


###
# Notes updating
###


@bp.route("/guest/<guest_id>/edit_notes", methods=["POST"])
@login_required
def edit_notes(guest_id):
    with db_cursor() as cursor:
        new_notes = request.form.get("notizen", "").strip()
        cursor.execute(
            "UPDATE gaeste SET notizen = %s, aktualisiert_am = %s WHERE id = %s",
            (new_notes, datetime.now(), guest_id),
        )
    flash("Notizen aktualisiert.", "success")
    return redirect(url_for("main.view_guest", guest_id=guest_id))


@bp.route("/guest/<guest_id>/edit_animal_notes/<int:animal_id>", methods=["POST"])
@login_required
def edit_animal_notes(guest_id, animal_id):
    with db_cursor() as cursor:
        new_notes = request.form.get("notizen", "").strip()
        cursor.execute(
            "UPDATE tiere SET notizen = %s, aktualisiert_am = %s WHERE id = %s",
            (new_notes, datetime.now(), animal_id),
        )
    flash("Tiernotizen aktualisiert.", "success")
    return redirect(url_for("main.view_guest", guest_id=guest_id))


###
# Guest & animal control
###
@bp.route("/guest/<guest_id>/deactivate", methods=["POST"])
@roles_required("admin")
@login_required
def deactivate_guest(guest_id):
    with db_cursor() as cursor:
        cursor.execute(
            "UPDATE gaeste SET status = 'Inaktiv', aktualisiert_am = %s WHERE id = %s",
            (datetime.now(), guest_id),
        )
    add_changelog(guest_id, "update", "Gast deaktiviert", cursor)
    flash("Gast wurde deaktiviert.", "success")
    return redirect(url_for("main.guest_list"))


@bp.route("/guest/<guest_id>/activate", methods=["POST"])
@roles_required("admin")
@login_required
def activate_guest(guest_id):
    with db_cursor() as cursor:
        cursor.execute(
            "UPDATE gaeste SET status = 'Aktiv', aktualisiert_am = %s WHERE id = %s",
            (datetime.now(), guest_id),
        )
    add_changelog(guest_id, "update", "Gast aktiviert", cursor)
    flash("Gast wurde aktiviert.", "success")
    return redirect(url_for("main.list_guests"))


@bp.route("/guest/<guest_id>/delete", methods=["POST"])
@roles_required("admin")
@login_required
def delete_guest(guest_id):
    with db_cursor() as cursor:
        # Zuerst das Löschen von abhängigen Datensätzen sicherstellen (z.B. Tiere, Futterhistorie, Changelog, ZAHLUNGEN WERDEN EXPLIZIT NICHT GELÖSCHT!)
        cursor.execute("DELETE FROM tiere WHERE gast_id = %s", (guest_id,))
        cursor.execute("DELETE FROM futterhistorie WHERE gast_id = %s", (guest_id,))
        cursor.execute("DELETE FROM changelog WHERE gast_id = %s", (guest_id,))
        cursor.execute("DELETE FROM gaeste WHERE id = %s", (guest_id,))
    session["guests_changed"] = True
    flash("Gast wurde vollständig gelöscht.", "success")
    return redirect(url_for("main.list_guests"))


@bp.route("/guest/<guest_id>/<int:animal_id>/delete", methods=["POST"])
@roles_required("admin", "editor")
@login_required
def delete_animal(guest_id, animal_id):
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM tiere WHERE id = %s", (animal_id,))
    add_changelog(guest_id, "delete", f"Tier gelöscht (ID: {animal_id})", cursor)
    flash("Tier wurde gelöscht.", "success")
    return redirect(url_for("main.view_guest", guest_id=guest_id))
