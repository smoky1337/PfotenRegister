from datetime import datetime
import secrets, string
from functools import wraps
from flask import abort, request
from flask_login import current_user

from .models import db, Guest, VisibleField


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
        FoodHistory.query.filter_by(gast_id=guest_id)
        .order_by(FoodHistory.futtertermin.desc())
        .all()
    )


def add_changelog(guest_id, change_type, description):
    """Füge einen Eintrag in das Änderungsprotokoll hinzu."""
    from .models import ChangeLog, db

    now = datetime.now()
    entry = ChangeLog(
        gast_id=guest_id,
        change_type=change_type,
        description=description,
        changed_by=current_user.username,
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

def get_form_value(fieldname):
    val = request.form.get(fieldname, None)
    if val:
        if val.strip() == '':
            return None
        else:
            return val.strip()
    return None


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
        Guest.query.with_entities(Guest.nummer)
        .order_by(Guest.nummer.desc())
        .all()
    )

    last_number = 0
    for r in rows:
        nummer = r.nummer
        if nummer and nummer.startswith(like_prefix):
            match = nummer.replace(like_prefix, "")
            if match.isdigit():
                last_number = int(match)
                break

    number_part = str(last_number + 1).zfill(count_n)
    return like_prefix + number_part


def get_visible_fields(model_name: str) -> list[str]:
    """Return a list of visible field names for the given model name."""
    fields = (
        db.session.query(VisibleField)
        .filter_by(model_name=model_name, is_visible=True)
        .all()
    )
    return [f.field_name for f in fields]

