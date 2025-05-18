import time

import mysql.connector
from mysql.connector import Error
from flask import current_app
from datetime import datetime
from .helpers import format_date, format_date_iso
from werkzeug.security import generate_password_hash


def get_db_connection():
    """
    Stellt eine Verbindung zur MySQL/MariaDB her.
    """
    try:
        connection = mysql.connector.connect(
            host=current_app.config["DB_HOST"],
            database=current_app.config["DB_DATABASE"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
            port=int(current_app.config["DB_PORT"]),
        )
        if connection.is_connected():
            db_info = connection.get_server_info()
            #print("Connected to MariaDB Server version %s", db_info)
        return connection
    except Error as e:
        current_app.logger.error("Error while connecting to MariaDB: %s", e)
        raise e


def init_db():
    """
    Initialisiert die Datenbank: Erzeugt Tabellen, falls sie nicht existieren, und fügt Beispieldaten ein.
    """
    with db_cursor() as cursor:
        # Tabelle für Gäste
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gaeste (
                id VARCHAR(255) UNIQUE NOT NULL PRIMARY KEY,
                nummer VARCHAR(255) NOT NULL,
                vorname VARCHAR(255) NOT NULL,
                nachname VARCHAR(255) NOT NULL,
                adresse VARCHAR(255),
                ort VARCHAR(255),
                plz VARCHAR(255),
                festnetz VARCHAR(50),
                mobil VARCHAR(50),
                email VARCHAR(255),
                geburtsdatum DATE,
                geschlecht ENUM('Frau', 'Herr', 'Divers', 'Unbekannt') DEFAULT 'Unbekannt',
                eintritt DATE NOT NULL,
                austritt DATE,
                vertreter_name VARCHAR(255) NULL,
                vertreter_telefon VARCHAR(50) NULL, 
                vertreter_email VARCHAR(255) NULL, 
                vertreter_adresse  VARCHAR(255) NULL,
                status ENUM('Aktiv', 'Inaktiv') NOT NULL DEFAULT 'Aktiv',
                beduerftigkeit VARCHAR(255),
                beduerftig_bis DATE,
                dokumente TEXT,
                notizen TEXT,
                erstellt_am DATE NOT NULL,
                aktualisiert_am DATE NOT NULL
            );
        """
        )

        # Tabelle für Tiere
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tiere (
                id INT AUTO_INCREMENT UNIQUE NOT NULL PRIMARY KEY,
                gast_id VARCHAR(255) NOT NULL,  -- Foreign key referencing gaeste
                art ENUM('Hund','Katze','Vogel','Nager', 'Sonstige') NOT NULL,
                rasse VARCHAR(100),
                name VARCHAR(100),
                geschlecht ENUM('M', 'F', 'Unbekannt') DEFAULT 'Unbekannt',
                farbe VARCHAR(100),
                kastriert ENUM('ja', 'nein', 'unbekannt'),
                identifikation VARCHAR(100),
                geburtsdatum DATE,
                gewicht_oder_groesse VARCHAR(50),
                krankheiten TEXT,
                unvertraeglichkeiten TEXT,
                futter ENUM('Misch','Trocken','Nass','Barf'),
                vollversorgung ENUM('ja', 'nein'),
                zuletzt_gesehen DATE,
                tierarzt VARCHAR(255),
                futtermengeneintrag TEXT,
                notizen TEXT,
                erstellt_am DATE NOT NULL,
                aktualisiert_am DATE NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                steuerbescheid_bis DATE,
                FOREIGN KEY (gast_id) REFERENCES gaeste(id) ON DELETE CASCADE
            );
        """
        )

        # Tabelle für Änderungsprotokoll
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS changelog (
                changelog_id INT AUTO_INCREMENT PRIMARY KEY,  -- Auto-increment ID for each log entry
                gast_id VARCHAR(255) NOT NULL,  -- Foreign key referencing gaeste
                change_type VARCHAR(255),
                description TEXT,
                changed_by VARCHAR(255),
                change_timestamp DATETIME,
                FOREIGN KEY (gast_id) REFERENCES gaeste(id) ON DELETE CASCADE
            );
        """
        )

        # Tabelle für Futtertermine
        cursor.execute(
            """
                CREATE TABLE IF NOT EXISTS futterhistorie (
                    entry_id INT AUTO_INCREMENT PRIMARY KEY,  -- Auto-increment ID for each log entry
                    gast_id VARCHAR(255) NOT NULL,  -- Foreign key referencing gaeste
                    futtertermin DATE,
                    FOREIGN KEY (gast_id) REFERENCES gaeste(id) ON DELETE CASCADE
                );
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS zahlungshistorie (
                id INT AUTO_INCREMENT PRIMARY KEY,
                gast_id VARCHAR(255) NOT NULL,
                zahlungstag DATE NOT NULL,
                futter_betrag DECIMAL(6,2) DEFAULT 0.00,
                zubehoer_betrag DECIMAL(6,2) DEFAULT 0.00,
                kommentar TEXT,
                erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                payment_open BOOLEAN NOT NULL DEFAULT FALSE,
                FOREIGN KEY (gast_id) REFERENCES gaeste(id) ON DELETE CASCADE
            );
            """
        )

        # Tabelle für Benutzer (User)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL
            );
        """
        )
    with db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM users")
        result = cursor.fetchone()
        if result["count"] == 0:
            admin_pass = generate_password_hash("admin")
            editor_pass = generate_password_hash("editor")
            benutzer_pass = generate_password_hash("benutzer")
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                ("admin", admin_pass, "admin"),
            )
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                ("editor", editor_pass, "editor"),
            )
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                ("benutzer", benutzer_pass, "user"),
            )

        create_settings_table()


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
        cursor = conn.cursor(dictionary=True)
        #print("[DB] Cursor opened")

        yield cursor  # <-- Hier arbeitest du mit dem Cursor!

        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            print(f"[DB] Long DB operation detected ({elapsed:.2f} seconds)")

        conn.commit()
        #print("[DB] Committed and closing cursor")
    except mysql.connector.Error as e:
        if conn:
            conn.rollback()
        print(f"[DB] MySQL error: {e}")
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DB] Unexpected error: {e}")
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
