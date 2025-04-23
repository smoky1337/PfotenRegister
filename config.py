import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get('SECRET_KEY', 'supergeheim')

# MySQL/MariaDB connection parameters.
DB_HOST = os.environ.get('DB_HOST', "thp-f.h.filess.io")
DB_DATABASE = os.environ.get('DB_DATABASE', "demopfotenregister_falldrynor")
DB_PORT = os.environ.get('DB_PORT', "61000")
DB_USER = os.environ.get('DB_USER', "demopfotenregister_falldrynor")
DB_PASSWORD = os.environ.get('DB_PASSWORD', "7eaca5d46c35e3c478f0fe3dfe4187ae600cc6f1")
