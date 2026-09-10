import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get('SECRET_KEY', 'supergeheim')

# MySQL/MariaDB connection parameters.
DB_HOST = os.environ['DB_HOST']
DB_DATABASE = os.environ['DB_DATABASE']
DB_PORT = os.environ['DB_PORT']
DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']

# File storage
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "gcs").lower()
LOCAL_STORAGE_PATH = os.environ.get(
    "LOCAL_STORAGE_PATH",
    os.path.join(BASE_DIR, "var", "uploads"),
)
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

# Performance diagnostics
SLOW_REQUEST_THRESHOLD_MS = float(os.environ.get("SLOW_REQUEST_THRESHOLD_MS", "1000"))
SLOW_QUERY_THRESHOLD_MS = float(os.environ.get("SLOW_QUERY_THRESHOLD_MS", "250"))
PERFORMANCE_LOG_ALL_WRITES = os.environ.get(
    "PERFORMANCE_LOG_ALL_WRITES",
    "true",
).lower() in {"1", "true", "yes", "on"}
