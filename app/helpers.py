import base64
import io
import os
import secrets
import string
from datetime import datetime, timedelta, date
from functools import wraps

import qrcode
import requests
from typing import Tuple
from flask import abort, request, current_app
from flask_login import current_user

from .models import Guest, FieldRegistry


def generate_unique_code(length=6):

    allowed_chars = (
        "".join(c for c in string.ascii_uppercase if c not in "IO")
        + "".join(c for c in string.ascii_lowercase if c not in "lo")
        + "".join(c for c in string.digits if c not in "01")
    )

    while True:
        code = "".join(secrets.choice(allowed_chars) for _ in range(length))
        exists = Guest.query.filter_by(id=code).first()
        if not exists:
            return code

def get_all_settings():
    from .db import db_cursor
    with db_cursor() as cursor:
        cursor.execute("SELECT setting_key, value FROM einstellungen")
        rows = cursor.fetchall()
        return {row["setting_key"]: {"value": row["value"]} for row in rows}


def format_date(dt):
    """

    :param dt: datetime in yyyy-mm-dd
    :return: String with dd-mm-yyyy
    """
    if type(dt) == datetime:
        return dt.strftime("%d-%m-%Y")
    if type(dt) == str:
        return datetime.strptime(dt, "%Y-%m-%d").strftime("%d-%m-%Y")


def format_date_iso(dt):
    """

    :param dt: datetime in dd-mm-yyyy
    :return: String with yyyy-mm-dd
    """
    if type(dt) == datetime:
        return dt.strftime("%Y-%m-%d")
    if type(dt) == str:
        return datetime.strptime(dt, "%d-%m-%Y").strftime("%Y-%m-%d")


def get_food_history(guest_id):
    """Return food history entries for a guest ordered by date desc."""
    from .models import FoodHistory

    return (
        FoodHistory.query.filter_by(guest_id=guest_id)
        .order_by(FoodHistory.distributed_on.desc())
        .all()
    )

def get_visible_fields(model):
    """Returns a list of field names marked as globally visible for the given model."""
    from .models import FieldRegistry

    model_name = model.__name__
    entries = FieldRegistry.query.filter_by(model_name=model_name, globally_visible=True).all()
    return [entry.field_name for entry in entries]


def add_changelog(guest_id, change_type, description):
    """Füge einen Eintrag in das Änderungsprotokoll hinzu."""
    from .models import ChangeLog, db
    now = datetime.now()
    entry = ChangeLog(
        guest_id=guest_id,
        change_type=change_type,
        description=description,
        user_id=current_user.id,
        change_timestamp=now,
    )
    db.session.add(entry)
    db.session.commit()


def roles_required(*roles):
    """
    Decorator to restrict access to users with one of the provided roles.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)

        return decorated_function

    return decorator

def user_has_access(required_level):
    role_order = {'User': 1, 'Editor': 2, 'Admin': 3}
    return role_order.get(current_user.role.capitalize(), 0) >= role_order.get(required_level, 0)

def get_form_value(fieldname):
    val = request.form.get(fieldname, None)
    if val:
        if val.strip() == '':
            return None
        else:
            return val.strip()
    return None

def is_different(new_value, old_value):
    if new_value in (None, "") and old_value in (None, ""):
        return False
    return str(new_value) != str(old_value)

def generate_guest_number() -> str:
    """Generate the next guest number based on the configured format."""
    from .models import Setting, Guest
    import re

    now = datetime.now()
    year_short = now.strftime("%y")
    year_long = now.strftime("%Y")
    month = now.strftime("%m")

    setting = Setting.query.filter_by(setting_key="guestNumberFormat").first()
    format_str = setting.value if setting else "YYMM-NNNN"

    def _expand_date_placeholders(template: str) -> str:
        return (
            template.replace("YYYY", year_long)
            .replace("YY", year_short)
            .replace("MM", month)
        )

    digit_blocks = list(re.finditer(r"(N+|0+)", format_str))
    if not digit_blocks:
        raise ValueError("Das Format muss mindestens einen Zahlen-Block enthalten (z.B. NNN oder 000).")

    # Use the *last* digit block so formats like "GTNN00NN00" can keep earlier N/0 as literal text.
    digit_block = digit_blocks[-1]
    digit_len = len(digit_block.group())

    prefix_template = format_str[:digit_block.start()]
    suffix_template = format_str[digit_block.end():]

    prefix = _expand_date_placeholders(prefix_template)
    suffix = _expand_date_placeholders(suffix_template)

    # Find the last used number matching this (prefix + digits + suffix) pattern.
    pattern = re.compile(
        r"^" + re.escape(prefix) + r"(\d{" + str(digit_len) + r"})" + re.escape(suffix) + r"$"
    )

    q = Guest.query.with_entities(Guest.number).filter(Guest.number.like(f"{prefix}%"))
    if suffix:
        q = q.filter(Guest.number.like(f"%{suffix}"))
    rows = q.order_by(Guest.number.desc()).limit(500).all()

    last_number = 0
    for (number,) in rows:
        if not number:
            continue
        m = pattern.match(number)
        if m:
            last_number = int(m.group(1))
            break

    number_part = str(last_number + 1).zfill(digit_len)
    return f"{prefix}{number_part}{suffix}"


def build_reminder_alerts(guest, animals=None, representative=None):
    """
    Return a list of reminder alerts for the given guest context.
    Each entry contains context, field label, stats, and status.
    """
    animals = animals or []
    alerts = []
    reminder_fields = FieldRegistry.query.filter_by(remindable=True).all()
    if not guest or not reminder_fields:
        return alerts

    today = datetime.today().date()

    def _to_date(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        return None

    def _register_alert(obj, field, ctx_label):
        raw_value = getattr(obj, field.field_name, None)
        interval_days = field.reminder_interval_days or 0
        value_date = _to_date(raw_value)
        if not value_date:
            alerts.append(
                {
                    "context": ctx_label,
                    "field_label": field.ui_label,
                    "status": "missing",
                    "interval_days": interval_days,
                    "value_date": None,
                    "due_date": None,
                    "overdue_days": None,
                }
            )
            return

        due_date = value_date + timedelta(days=interval_days)
        overdue_days = (today - due_date).days
        if overdue_days >= 0:
            alerts.append(
                {
                    "context": ctx_label,
                    "field_label": field.ui_label,
                    "status": "overdue",
                    "interval_days": interval_days,
                    "value_date": value_date,
                    "due_date": due_date,
                    "overdue_days": overdue_days,
                }
            )

    for field in reminder_fields:
        if field.model_name == "Guest":
            _register_alert(
                guest,
                field,
                f"Gast · {guest.firstname} {guest.lastname}",
            )
        elif field.model_name == "Animal":
            allowed_species = [
                specie.strip()
                for specie in (field.reminder_species or "").split(",")
                if specie and specie.strip()
            ]
            for animal in animals:
                if hasattr(animal, "status") and not animal.status:
                    continue
                if getattr(animal, "died_on", None):
                    continue
                if allowed_species and (animal.species or "") not in allowed_species:
                    continue
                _register_alert(
                    animal,
                    field,
                    f"Tier · {animal.name or 'Unbenannt'}",
                )
        elif field.model_name == "Representative" and representative:
            _register_alert(
                representative,
                field,
                f"Vertreter · {representative.name or 'Unbekannt'}",
            )

    return alerts


def _render_guest_card_template(template: str, guest: Guest) -> str:
    """
    Replace simple placeholders in the email template.
    Supported: {{guest_id}}, {{guest_number}}, {{first_name}}, {{last_name}}
    """
    replacements = {
        "{{guest_id}}": str(guest.id),
        "{{guest_number}}": guest.number or "",
        "{{first_name}}": guest.firstname or "",
        "{{last_name}}": guest.lastname or "",
    }
    rendered = template or ""
    for needle, val in replacements.items():
        rendered = rendered.replace(needle, val)
    return rendered


def _settings_value(settings: dict, key: str) -> str:
    entry = settings.get(key, {})
    val = entry.get("value") if isinstance(entry, dict) else None
    if val is None:
        try:
            from .models import Setting

            row = Setting.query.filter_by(setting_key=key).first()
            val = row.value if row else None
        except Exception:  # noqa: BLE001
            val = None
    return str(val).strip() if val is not None else ""


def _build_guest_card_email_html(settings: dict, guest: Guest, body_html: str) -> str:
    pfoten_logo = "https://pfotenregister.com/images/logo.png"
    custom_logo = _settings_value(settings, "logourl")
    custom_logo = custom_logo if custom_logo.startswith("http") else ""

    organisation_name = _settings_value(settings, "name") or "PfotenRegister"

    address = _settings_value(settings, "emailFooterAddress")
    phone = _settings_value(settings, "emailFooterPhone")
    email = _settings_value(settings, "emailFooterEmail") or (os.environ.get("REPLY_TO") or "").strip() or _settings_value(settings, "adminEmail")
    website = _settings_value(settings, "emailFooterWebsite")
    extra = _settings_value(settings, "emailFooterExtra")

    logo_row = (
        f"<img src='{pfoten_logo}' width='140' alt='PfotenRegister' style='display:block; height:auto;'>"
    )
    if custom_logo:
        logo_row = (
            f"<table role='presentation' cellpadding='0' cellspacing='0' border='0' width='100%'>"
            f"<tr>"
            f"<td align='left' style='padding:0;'>"
            f"<img src='{pfoten_logo}' width='140' alt='PfotenRegister' style='display:block; height:auto;'>"
            f"</td>"
            f"<td align='right' style='padding:0;'>"
            f"<img src='{custom_logo}' width='140' alt='{organisation_name}' style='display:block; height:auto;'>"
            f"</td>"
            f"</tr>"
            f"</table>"
        )

    footer_lines = []
    if organisation_name:
        footer_lines.append(f"<strong style='color:#111827;'>{organisation_name}</strong>")
    if address:
        footer_lines.append(address.replace("\n", "<br>"))
    if phone:
        footer_lines.append(f"Telefon: {phone}")
    if email:
        footer_lines.append(f"E-Mail: <a href='mailto:{email}' style='color:#2563eb; text-decoration:none;'>{email}</a>")
    if website:
        href = website if website.startswith("http") else f"https://{website}"
        footer_lines.append(f"Web: <a href='{href}' style='color:#2563eb; text-decoration:none;'>{website}</a>")
    if extra:
        footer_lines.append(extra.replace("\n", "<br>"))

    footer_html = ""
    if footer_lines:
        footer_html = (
            "<hr style='border:none; border-top:1px solid #e5e7eb; margin:24px 0;'>"
            f"<div style='font-size:12px; line-height:18px; color:#6b7280;'>"
            f"{'<br>'.join(footer_lines)}"
            "</div>"
            "<div style='margin-top:10px; font-size:11px; line-height:16px; color:#9ca3af;'>Gesendet über PfotenRegister</div>"
        )

    return f"""\
<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PfotenRegister</title>
  </head>
  <body style="margin:0; padding:0; background:#f3f4f6;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
      <tr>
        <td align="center" style="padding:24px 12px;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:640px; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 2px 12px rgba(0,0,0,.06);">
            <tr>
              <td style="padding:20px 20px 0 20px;">
                {logo_row}
              </td>
            </tr>
            <tr>
              <td style="padding:16px 20px 0 20px; font-family:Arial, Helvetica, sans-serif;">
                <div style="font-size:16px; line-height:24px; color:#111827;">
                  {body_html}
                </div>
                <div style="margin-top:16px; padding:14px 16px; background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px; font-size:13px; line-height:20px; color:#111827;">
                  <div><strong>Gast-ID:</strong> {guest.id}</div>
                  <div><strong>Gast-Nr.:</strong> {guest.number}</div>
                  <div style="margin-top:10px; color:#6b7280;">Der QR-Code ist als Anhang beigefügt.</div>
                </div>
                {footer_html}
              </td>
            </tr>
            <tr>
              <td style="padding:16px 20px 18px 20px; font-family:Arial, Helvetica, sans-serif; font-size:11px; line-height:16px; color:#9ca3af;">
                Diese E-Mail wurde automatisch versendet. Bitte antworte bei Rückfragen über die hinterlegte Antwortadresse.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def send_guest_card_email(guest: Guest, settings: dict) -> Tuple[bool, str]:
    """
    Send a guest card email with an embedded QR code via Brevo (Sendinblue) SMTP API.
    Returns (success, message).
    """
    if not guest.email:
        return False, "Keine E-Mail-Adresse hinterlegt."

    api_key = os.environ.get("MAIL_KEY")
    if not api_key:
        return False, "MAIL_KEY (Brevo API Key) nicht gesetzt."

    reply_to_email = os.environ.get("REPLY_TO")
    if not reply_to_email:
        return False, "REPLY_TO (Antwortadresse) nicht gesetzt."

    sender_email = settings.get("adminEmail", {}).get("value")
    if not sender_email:
        return False, "Absenderadresse fehlt (Admin-E-Mail)."

    sender_name = settings.get("name", {}).get("value") or "PfotenRegister"

    subject_template = settings.get("guestCardEmailSubject", {}).get("value") or "Deine PfotenRegister Gästekarte"
    body_template = settings.get("guestCardEmailBody", {}).get("value") or (
        "Hallo {{first_name}},<br><br>"
        "hier ist deine digitale Gästekarte. Du kannst den QR-Code direkt vorzeigen.<br><br>"
        "Viele Grüße,<br>PfotenRegister Team"
    )

    subject = _render_guest_card_template(subject_template, guest)
    body_html = _render_guest_card_template(body_template, guest)

    qr_img = qrcode.make(str(guest.id))
    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    html = _build_guest_card_email_html(settings, guest, body_html)

    try:
        payload = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": guest.email}],
            "replyTo": {"email": reply_to_email},
            "subject": subject,
            "htmlContent": html,
            "attachment": [
                {
                    "content": qr_b64,
                    "name": f"guest-card-{guest.id}.png",
                }
            ],
        }

        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30,
        )
        if resp.status_code in (200, 201, 202):
            return True, "E-Mail versendet."
        current_app.logger.error("Brevo send failed (%s): %s", resp.status_code, resp.text)
        return False, f"Versand fehlgeschlagen: {resp.status_code} {resp.text}"
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("E-Mail Versand fehlgeschlagen: %s", exc)
        return False, f"Versand fehlgeschlagen: {exc}"


from uuid import uuid4
from flask import current_app


def upload_file(file_storage, owner_id: str) -> str:
    """
    Uploads a Werkzeug FileStorage (from request.files) to GCS under
    {owner_type}/{owner_id}/{uuid4()}{file_ext}.
    Returns the full GCS path (object name).
    """
    ext = "" if "." not in file_storage.filename else file_storage.filename.rsplit(".", 1)[1]
    filename = f"{uuid4()}.{ext}" if ext else str(uuid4())
    blob_path = f"guest/{owner_id}/{filename}"

    bucket = current_app.bucket  # from create_app()
    blob = bucket.blob(blob_path)
    # stream directly from the uploaded file
    blob.upload_from_file(
        file_storage.stream,
        content_type=file_storage.mimetype
    )
    return blob_path


def generate_download_url(blob_path: str, expires_minutes: int = 10) -> str:
    blob = current_app.bucket.blob(blob_path)
    return blob.generate_signed_url(
        expiration=timedelta(minutes=expires_minutes),
        version="v4",  # <— force V4
        # service_account_email=current_app.config["GCS_SIGNER_EMAIL"]
    )


def delete_blob(blob_path: str):
    """Deletes the given object from GCS."""
    bucket = current_app.bucket
    blob = bucket.blob(blob_path)
    blob.delete()

def is_active(setting:str):
    """Check if a setting is active based on the app config."""
    settings = current_app.config.get("SETTINGS", {})
    if setting not in settings.keys():
        raise ValueError(f"Setting '{setting}' not found in configuration.")
    return settings.get(setting, {}).get("value", "Aktiv") == "Aktiv"
