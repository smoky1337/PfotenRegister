import time

import pymysql
from flask import current_app
from datetime import datetime
from .helpers import format_date, format_date_iso
from werkzeug.security import generate_password_hash
from .models import db


def get_db_connection():
    """Return a raw DBAPI connection using SQLAlchemy's engine."""
    engine = db.get_engine(app=current_app)
    return engine.raw_connection()



def get_setting_value(key):
    with db_cursor() as cursor:
        cursor.execute("SELECT value FROM einstellungen WHERE setting_key = %s", (key,))
        result = cursor.fetchone()
        if result:
            return result["value"]
        else:
            return None


from contextlib import contextmanager


@contextmanager
def db_cursor(timeout_seconds=10):
    conn = None
    cursor = None
    start_time = time.time()
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        #print("[DB] Cursor opened")

        yield cursor  # <-- Hier arbeitest du mit dem Cursor!

        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            print(f"[DB] Long DB operation detected ({elapsed:.2f} seconds)")

        conn.commit()
        #print("[DB] Committed and closing cursor")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DB] DB error: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
            #print("[DB] Cursor closed")
        if conn:
            conn.close()
            #print("[DB] Connection closed")


def create_settings_table():
    with db_cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS einstellungen (
                id INT AUTO_INCREMENT PRIMARY KEY,
                setting_key VARCHAR(255) UNIQUE NOT NULL,
                value TEXT NOT NULL,
                description TEXT
            );
        """
        )
