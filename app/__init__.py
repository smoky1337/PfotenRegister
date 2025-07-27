import os

from flask import Flask
from flask_login import LoginManager
from google.cloud import storage
from google.oauth2 import service_account

from .auth import get_user
from .models import db as sqlalchemy_db, Setting


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

    app.refresh_settings = refresh_settings

    with app.app_context():
        sqlalchemy_db.create_all()
        refresh_settings()

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
    from .routes.attachement_routes import att_bp

    app.register_blueprint(guest_bp)
    app.register_blueprint(animal_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(food_bp)
    app.register_blueprint(att_bp)

    from .auth import auth_bp

    app.register_blueprint(auth_bp)
    from .routes.admin.admin_routes import admin_bp
    from .routes.admin.import_export_routes import admin_io_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_io_bp)

    return app
