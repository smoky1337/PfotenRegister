import csv
from app import create_app


def import_settings_from_csv(csv_path="settings.csv", overwrite_existing=False):
    app = create_app()

    with app.app_context():
        from app.db import get_db_connection
        conn = get_db_connection()

        cursor = conn.cursor()

        with open(csv_path, mode='r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                print(row)
                setting = row['setting_key']
                value = row['value']
                description = row.get('description', '')

                # Prüfen, ob Setting existiert
                cursor.execute("SELECT COUNT(*) FROM einstellungen WHERE setting_key = %s", (setting,))
                exists = cursor.fetchone()[0]

                if exists:
                    if overwrite_existing:
                        cursor.execute("""
                            UPDATE einstellungen
                            SET value = %s, description = %s
                            WHERE setting_key = %s
                        """, (value, description, setting))
                        print(f"🔁 Setting '{setting}' wurde aktualisiert.")
                    else:
                        print(f"⏩ Setting '{setting}' existiert bereits – wird übersprungen.")
                else:
                    cursor.execute("""
                        INSERT INTO einstellungen (setting_key, value, description)
                        VALUES (%s, %s, %s)
                    """, (setting, value, description))
                    print(f"➕ Setting '{setting}' wurde hinzugefügt.")

        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Import abgeschlossen.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Importiere Einstellungen aus einer CSV-Datei.")
    parser.add_argument('--overwrite', action='store_true', help="Existierende Werte überschreiben")
    parser.add_argument('--file', type=str, default="settings.csv", help="Pfad zur CSV-Datei")

    args = parser.parse_args()
    import_settings_from_csv(csv_path=args.file, overwrite_existing=args.overwrite)