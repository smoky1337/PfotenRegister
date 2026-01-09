import os
from typing import Optional

from flask import Flask, request
from flask_login import LoginManager
from google.cloud import storage
from google.oauth2 import service_account
from sqlalchemy import Date, DateTime

from .auth import get_user
from .models import db as sqlalchemy_db, Setting, FieldRegistry

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


def create_app():
    app = Flask(__name__)
    app.config.from_pyfile("../config.py")

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

    db_uri = (
        f"mysql+pymysql://{app.config['DB_USER']}:{app.config['DB_PASSWORD']}"
        f"@{app.config['DB_HOST']}:{app.config['DB_PORT']}/{app.config['DB_DATABASE']}"
    )
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    sqlalchemy_db.init_app(app)

    # Push application context before initializing the database.
    from . import db #not sqlalchemy yet

    @app.context_processor
    def inject_settings():
        return dict(settings=app.config.get("SETTINGS", {}))

    @app.context_processor
    def inject_help_link():
        return {"help_link": _resolve_help_link(request.endpoint)}

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
    from .routes.food_plan_routes import food_plan_bp
    from .routes.attachement_routes import att_bp
    from .routes.location_routes import location_bp

    app.register_blueprint(guest_bp)
    app.register_blueprint(animal_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(food_bp)
    app.register_blueprint(food_plan_bp)
    app.register_blueprint(att_bp)
    app.register_blueprint(location_bp)

    from .auth import auth_bp

    app.register_blueprint(auth_bp)
    from .routes.admin.admin_routes import admin_bp
    from .routes.admin.import_export_routes import admin_io_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_io_bp)

    return app
