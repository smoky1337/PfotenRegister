from flask import Flask
from flask_login import LoginManager
from .auth import get_user
from .models import db as sqlalchemy_db, Setting


def create_app():
    app = Flask(__name__)
    app.config.from_pyfile("../config.py")
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

    app.register_blueprint(guest_bp)
    app.register_blueprint(animal_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(food_bp)
    from .auth import auth_bp

    app.register_blueprint(auth_bp)
    from .routes.admin.admin_routes import admin_bp
    from .routes.admin.import_export_routes import admin_io_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_io_bp)

    return app
