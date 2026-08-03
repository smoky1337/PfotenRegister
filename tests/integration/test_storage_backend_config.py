from app import create_app
from app.storage import GoogleCloudStorage


class _FakeBucket:
    pass


class _FakeStorageClient:
    def __init__(self, *args, **kwargs):
        self.requested_bucket = None

    def bucket(self, bucket_name):
        self.requested_bucket = bucket_name
        return _FakeBucket()


def test_gcs_backend_uses_google_storage_client(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr("app.gcs_storage.Client", _FakeStorageClient)

    app = create_app(
        {
            "GCS_BUCKET_NAME": "existing-deployment-bucket",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STORAGE_BACKEND": "gcs",
            "TESTING": False,
        }
    )

    assert isinstance(app.storage_client, _FakeStorageClient)
    assert app.storage_client.requested_bucket == "existing-deployment-bucket"
    assert isinstance(app.file_storage, GoogleCloudStorage)
