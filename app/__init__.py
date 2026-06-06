import os
import traceback
from typing import Optional

from flask import Flask, request, url_for
from flask_login import LoginManager
from google.cloud import storage
from google.oauth2 import service_account
from sqlalchemy import Date, DateTime
from werkzeug.exceptions import HTTPException
from markupsafe import escape

from .auth import get_user
from .models import db as sqlalchemy_db, Setting, FieldRegistry, PaymentPackage

DOCS_BASE_URL = "https://docs.pfotenregister.com"

HELP_LINKS = {
    "auth.login": "getting-started",
    "guest.index": "getting-started",
    "guest.list_guests": "guests/view_all",
    "guest.view_guest": "guests/view_one",
    "guest.register_guest": "guests/create",
    "guest.edit_guest": "guests/edit",
    "guest.list_messages": "messages",
    "guest.deactivate_guest": "guests/status",
    "guest.activate_guest": "guests/status",
    "guest.delete_guest": "guests/delete",
    "animal.register_animal": "animals/create",
    "animal.edit_animal": "animals/edit",
    "animal.list_animals": "animals/list",
    "medical.list_medical_events": "guests/view_one",
    "medical.create_medical_event": "guests/view_one",
    "medical.edit_medical_event": "guests/view_one",
    "attachment.list_attachments": "attachments",
    "payment.list_payments": "payments/list",
    "admin.dashboard": "admin/dashboard",
    "admin.list_users": "admin/users/edit",
    "admin.edit_user": "admin/users/edit",
    "admin.register_user": "admin/users/create",
    "admin.export_transactions": "admin/reports",
    "admin_io.import_data": "admin/data",
    "admin_io.preview_import": "admin/data",
    "admin_io.export_data": "admin/data",
}

SETTINGS_TAB_LINKS = {
    "general": "admin/settings/pages",
    "fields": "admin/settings/fields",
    "reminders": "admin/settings/fields",
    "foodtags": "admin/settings/tags",
}


def _format_help_url(path: Optional[str]) -> str:
    if not path:
        return DOCS_BASE_URL
    clean_path = path.strip("/")
    return f"{DOCS_BASE_URL}/{clean_path}/"


def _resolve_help_link(endpoint: Optional[str]) -> str:
    if not endpoint:
        return DOCS_BASE_URL
    if endpoint == "admin.edit_settings":
        tab = request.args.get("tab", "general")
        path = SETTINGS_TAB_LINKS.get(tab, SETTINGS_TAB_LINKS["general"])
    else:
        path = HELP_LINKS.get(endpoint)
    return _format_help_url(path)


def create_app(config_overrides: Optional[dict] = None):
    app = Flask(__name__)
    app.config.from_pyfile("../config.py")
    if config_overrides:
        app.config.update(config_overrides)

    if app.config.get("TESTING"):
        app.storage_client = None
        app.bucket = None
    else:
        # If you’ve set GOOGLE_APPLICATION_CREDENTIALS in the env, load a SA key.
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path:
            creds = service_account.Credentials.from_service_account_file(creds_path)
            storage_client = storage.Client(credentials=creds, project=os.environ.get("GCP_PROJECT"))
        else:
            # On Cloud Run, ADC is automatically provided via the instance’s SA
            storage_client = storage.Client()

        # Make bucket object global for easy import
        app.storage_client = storage_client
        app.bucket = storage_client.bucket(app.config["GCS_BUCKET_NAME"])  # type: ignore

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        db_uri = (
            f"mysql+pymysql://{app.config['DB_USER']}:{app.config['DB_PASSWORD']}"
            f"@{app.config['DB_HOST']}:{app.config['DB_PORT']}/{app.config['DB_DATABASE']}"
        )
        app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    sqlalchemy_db.init_app(app)

    # Push application context before initializing the database.
    from . import db #not sqlalchemy yet

    @app.context_processor
    def inject_settings():
        return dict(settings=app.config.get("SETTINGS", {}))

    @app.context_processor
    def inject_help_link():
        return {"help_link": _resolve_help_link(request.endpoint)}

    @app.context_processor
    def inject_payment_packages():
        packages = (
            PaymentPackage.query.filter_by(active=True)
            .order_by(PaymentPackage.display_order.asc(), PaymentPackage.name.asc())
            .all()
        )
        return {"payment_packages": packages}

    @app.errorhandler(Exception)
    def render_error_page(error):
        """Render a standalone German error page for uncaught application errors."""
        status_code = error.code if isinstance(error, HTTPException) else 500
        if not isinstance(error, HTTPException):
            app.logger.exception("Uncaught application error", exc_info=error)
            try:
                sqlalchemy_db.session.rollback()
            except Exception:
                app.logger.exception("Database rollback failed while rendering error page")

        try:
            home_url = url_for("guest.index")
        except Exception:
            home_url = "/"

        if isinstance(error, HTTPException) and status_code == 404:
            headline = "Diese Seite wurde nicht gefunden."
            intro = "Der angeforderte Inhalt ist nicht verfügbar."
        else:
            headline = "Entschuldigung, da ist etwas schiefgelaufen."
            intro = "Bitte gehe zurück zur Startseite und versuche es erneut."

        if isinstance(error, HTTPException):
            trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        else:
            trace = traceback.format_exc()

        html = f"""<!doctype html>
<html lang="de">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Fehler - PfotenRegister</title>
    <style>
        body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 24px;
            font-family: Arial, sans-serif;
            color: #1f2a2e;
            background: #eef4f2;
        }}
        main {{
            width: min(960px, 100%);
            padding: 28px;
            border-radius: 18px;
            background: #fff;
            box-shadow: 0 18px 40px rgba(18, 31, 34, 0.12);
        }}
        h1 {{
            margin: 0 0 10px;
            font-size: 28px;
        }}
        p {{
            margin: 0 0 18px;
            color: #5f6f74;
        }}
        a {{
            display: inline-block;
            margin-bottom: 22px;
            padding: 10px 14px;
            border-radius: 10px;
            background: #1b4750;
            color: #fff;
            text-decoration: none;
            font-weight: 700;
        }}
        details {{
            margin-top: 12px;
        }}
        summary {{
            cursor: pointer;
            font-weight: 700;
        }}
        pre {{
            overflow: auto;
            max-height: 420px;
            padding: 14px;
            border-radius: 12px;
            background: #172327;
            color: #f7faf8;
            white-space: pre-wrap;
            word-break: break-word;
        }}
    </style>
</head>
<body>
    <main>
        <h1>{escape(headline)}</h1>
        <p>{escape(intro)}</p>
        <a href="{escape(home_url)}">Zur Startseite</a>
        <details open>
            <summary>Technische Details</summary>
            <pre>{escape(trace)}</pre>
        </details>
    </main>
</body>
</html>"""
        return html, status_code

    def load_settings():
        rows = Setting.query.all()
        settings = {}
        for row in rows:
            settings[row.setting_key] = {
                "value": row.value,
                "description": row.description,
            }
        return settings

    def refresh_settings():
        app.config["SETTINGS"] = load_settings()

    def default_label(name: str) -> str:
        return name.replace("_", " ").capitalize()


    app.refresh_settings = refresh_settings

    with app.app_context():
        sqlalchemy_db.create_all()
        refresh_settings()

        # Populate FieldRegistry
        models = [mapper.class_ for mapper in sqlalchemy_db.Model.registry.mappers]
        t = 0
        for model in models:
            if not hasattr(model, '__tablename__'):
                continue
            model_name = model.__name__
            if model_name not in ('Guest','Animal','Representative'):
                continue
            for column in model.__table__.columns:
                field_name = column.name

                # Check if already exists
                exists = FieldRegistry.query.filter_by(
                    model_name=model_name,
                    field_name=field_name
                ).first()

                if not exists:
                    is_optional = column.nullable or column.default is not None or column.server_default is not None
                    is_remindable = isinstance(column.type, (Date, DateTime))
                    sqlalchemy_db.session.add(
                        FieldRegistry(
                            model_name=model_name,
                            field_name=field_name,
                            globally_visible=True,
                            optional=is_optional,
                            visibility_level="User",
                            editability_level="Editor",
                            ui_label=default_label(field_name),
                            show_inline=True,
                            display_order=0,
                            remindable=is_remindable,
                        )
                    )
                    t = t + 1

        sqlalchemy_db.session.commit()
        print("FieldRegistry populated with %d entries" % t)


        

    # Setup Login Manager
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return get_user(user_id)

    # Register blueprints
    from .routes.guest_routes import guest_bp
    from .routes.animal_routes import animal_bp
    from .routes.payment_routes import payment_bp
    from .routes.food_routes import food_bp
    from .routes.accessories_routes import accessories_bp
    from .routes.food_plan_routes import food_plan_bp
    from .routes.medical_routes import medical_bp
    from .routes.health_routes import health_bp
    from .routes.attachement_routes import att_bp
    from .routes.location_routes import location_bp

    app.register_blueprint(guest_bp)
    app.register_blueprint(animal_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(food_bp)
    app.register_blueprint(accessories_bp)
    app.register_blueprint(food_plan_bp)
    app.register_blueprint(medical_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(att_bp)
    app.register_blueprint(location_bp)

    from .auth import auth_bp

    app.register_blueprint(auth_bp)
    from .routes.admin.admin_routes import admin_bp
    from .routes.admin.import_export_routes import admin_io_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_io_bp)

    return app
