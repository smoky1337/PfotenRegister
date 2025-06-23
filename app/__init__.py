from flask import Flask
from flask_login import LoginManager
from .auth import get_user
from .db import db_cursor


def create_app():
    app = Flask(__name__)
    app.config.from_pyfile("../config.py")

    # Push application context before initializing the database.
    from . import db

    @app.context_processor
    def inject_settings():
        return dict(settings=app.config.get("SETTINGS", {}))

    def load_settings():
        with db_cursor() as cursor:
            cursor.execute("SELECT setting_key, value, description FROM einstellungen")
            rows = cursor.fetchall()

        settings = {}
        for row in rows:
            settings[row["setting_key"]] = {
                "value": row["value"],
                "description": row["description"],
            }
        return settings

    def refresh_settings():
        app.config["SETTINGS"] = load_settings()

    app.refresh_settings = refresh_settings

    with app.app_context():
        db.init_db()
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

    app.register_blueprint(guest_bp)
    app.register_blueprint(animal_bp)
    app.register_blueprint(payment_bp)
    from .auth import auth_bp

    app.register_blueprint(auth_bp)
    from .admin import admin_bp

    app.register_blueprint(admin_bp)

    return app
