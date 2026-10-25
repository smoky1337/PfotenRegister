import io

import pytest

from app.storage import LocalFileStorage, StoredFileNotFound


def test_local_storage_upload_download_and_delete(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    object_name = "guest/123/document.txt"

    storage.upload(object_name, io.BytesIO(b"local content"), "text/plain")
    stored_file = storage.download(object_name)

    assert stored_file.data == b"local content"
    assert stored_file.content_type == "text/plain"

    storage.delete(object_name)
    with pytest.raises(StoredFileNotFound):
        storage.download(object_name)


def test_local_storage_rejects_paths_outside_root(tmp_path):
    storage = LocalFileStorage(str(tmp_path))

    with pytest.raises(ValueError, match="escapes"):
        storage.upload("../outside.txt", io.BytesIO(b"nope"))
