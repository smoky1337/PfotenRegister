import pytest
from app import create_app
import functools
from dotenv import load_dotenv
import os
# Lade die .env-Datei beim Start von pytest
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', os.environ.get("ENV")))
load_dotenv(dotenv_path)

@pytest.fixture
def app():
    app = create_app()
    return app

@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    def do_login(username="admin", password="admin"):
        return client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)
    return do_login

