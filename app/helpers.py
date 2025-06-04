from datetime import datetime
import secrets, string
from functools import wraps
from flask import abort, request
from flask_login import current_user


def generate_unique_code(length=6):
    from .db import db_cursor

    allowed_chars = (
        "".join(c for c in string.ascii_uppercase if c not in "IO")
        + "".join(c for c in string.ascii_lowercase if c not in "lo")
        + "".join(c for c in string.digits if c not in "01")
    )

    with db_cursor() as cursor:
        while True:
            code = "".join(secrets.choice(allowed_chars) for _ in range(length))
            cursor.execute("SELECT 1 FROM gaeste WHERE id = %s", (code,))
            if not cursor.fetchone():
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
    from .db import db_cursor

    with db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM futterhistorie WHERE gast_id = %s ORDER BY futtertermin DESC",
            (guest_id,),
        )
        return cursor.fetchall()


def add_changelog(guest_id, change_type, description, cursor=None):
    """Fügt einen neuen Changelog-Eintrag hinzu. Kann optional einen offenen Cursor verwenden."""
    now = datetime.now()

    if cursor:
        cursor.execute(
            """
            INSERT INTO changelog (gast_id, change_type, description, change_timestamp, changed_by)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (guest_id, change_type, description, now, current_user.username),
        )
    else:
        from .db import db_cursor

        with db_cursor() as new_cursor:
            new_cursor.execute(
                """
                INSERT INTO changelog (gast_id, change_type, description, change_timestamp, changed_by)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (guest_id, change_type, description, now, current_user.username),
            )


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
    from app.db import db_cursor
    import re

    now = datetime.now()
    year_short = now.strftime("%y")  # z.B. "25"
    year_long = now.strftime("%Y")   # z.B. "2025"
    month = now.strftime("%m")       # z.B. "06"

    with db_cursor() as cursor:
        # Format abrufen
        cursor.execute(
            "SELECT value FROM einstellungen WHERE setting_key = %s",
            ("guestNumberFormat",)
        )
        format_str = cursor.fetchone()["value"]

        # Längsten NNN-Block finden
        n_blocks = list(re.finditer(r"N+", format_str))
        if not n_blocks:
            raise ValueError("Das Format muss mindestens einen N-Block enthalten.")
        longest_n_block = max(n_blocks, key=lambda m: len(m.group()))
        count_n = len(longest_n_block.group())

        # Like-Prefix aufbauen
        like_prefix = format_str[:longest_n_block.start()]
        like_prefix = like_prefix.replace("YYYY", year_long)
        like_prefix = like_prefix.replace("YY", year_short)
        like_prefix = like_prefix.replace("MM", month)

        # Alle Nummern holen, absteigend sortiert
        cursor.execute("SELECT nummer FROM gaeste ORDER BY nummer DESC")
        rows = cursor.fetchall()

        last_number = 0
        for r in rows:
            nummer = r["nummer"]
            if nummer.startswith(like_prefix):
                match = nummer.replace(like_prefix, "")
                if match.isdigit():
                    last_number = int(match)
                    break  # erste passende (höchste) Nummer gefunden

        number_part = str(last_number + 1).zfill(count_n)
        result = like_prefix + number_part

    return result