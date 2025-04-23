from datetime import datetime
import secrets, string
from functools import wraps
from flask import abort
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
            INSERT INTO changelog (gast_id, change_type, description, change_timestamp)
            VALUES (%s, %s, %s, %s)
            """,
            (guest_id, change_type, description, now),
        )
    else:
        from .db import db_cursor

        with db_cursor() as new_cursor:
            new_cursor.execute(
                """
                INSERT INTO changelog (gast_id, change_type, description, change_timestamp)
                VALUES (%s, %s, %s, %s)
                """,
                (guest_id, change_type, description, now),
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
