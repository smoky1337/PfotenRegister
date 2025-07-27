import secrets
import string
from datetime import datetime, timedelta
from functools import wraps

from flask import abort, request
from flask_login import current_user

from .models import Guest


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

    n_blocks = list(re.finditer(r"N+", format_str))
    if not n_blocks:
        raise ValueError("Das Format muss mindestens einen N-Block enthalten.")
    longest_n_block = max(n_blocks, key=lambda m: len(m.group()))
    count_n = len(longest_n_block.group())

    like_prefix = format_str[:longest_n_block.start()]
    like_prefix = like_prefix.replace("YYYY", year_long)
    like_prefix = like_prefix.replace("YY", year_short)
    like_prefix = like_prefix.replace("MM", month)

    rows = (
        Guest.query.with_entities(Guest.number)
        .order_by(Guest.number.desc())
        .all()
    )

    last_number = 0
    for r in rows:
        number = r.number
        if number and number.startswith(like_prefix):
            match = number.replace(like_prefix, "")
            if match.isdigit():
                last_number = int(match)
                break

    number_part = str(last_number + 1).zfill(count_n)
    return like_prefix + number_part


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
    """
    Returns a signed URL valid for `expires_minutes` minutes to download the object.
    """
    bucket = current_app.bucket
    blob = bucket.blob(blob_path)
    return blob.generate_signed_url(expiration=timedelta(minutes=expires_minutes))


def delete_blob(blob_path: str):
    """Deletes the given object from GCS."""
    bucket = current_app.bucket
    blob = bucket.blob(blob_path)
    blob.delete()
