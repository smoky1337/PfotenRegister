import pytest
from app import create_app
from app.models import db, Guest, Animal, User, PaymentHistory, FoodHistory, ChangeLog
import functools
from dotenv import load_dotenv
import os
from  datetime import datetime

# Lade die .env-Datei beim Start von pytest
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', os.environ.get("ENV")))
load_dotenv(dotenv_path)

@pytest.fixture(scope="session")
def app():
    app = create_app()
    with app.app_context():
        yield app
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()

test_start_time = datetime.utcnow()
@pytest.fixture(scope="session", autouse=True)
def cleanup_db(app):
    """Remove only the records created during a test run."""
    with app.app_context():
        start_animal = db.session.query(db.func.max(Animal.id)).scalar() or 0
        start_payment = db.session.query(db.func.max(PaymentHistory.id)).scalar() or 0
        start_food = db.session.query(db.func.max(FoodHistory.entry_id)).scalar() or 0
        start_log = db.session.query(db.func.max(ChangeLog.changelog_id)).scalar() or 0
        start_guests = {g.id for g in db.session.query(Guest.id).all()}
    yield
    with app.app_context():
        db.session.query(Guest).filter(~Guest.id.in_(start_guests)).delete(synchronize_session=False)
        db.session.query(ChangeLog).filter(ChangeLog.changelog_id > start_log).delete()
        db.session.query(PaymentHistory).filter(PaymentHistory.id > start_payment).delete()
        db.session.query(FoodHistory).filter(FoodHistory.entry_id > start_food).delete()
        db.session.query(Animal).filter(Animal.id > start_animal).delete()
        db.session.query(User).filter(User.username == "pytest_user").delete()
        db.session.commit()


@pytest.fixture
def login(client):
    def do_login(username="admin", password="admin"):
        return client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)
    return do_login
