import mimetypes
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional

from google.api_core.exceptions import NotFound
from google.cloud.storage import Bucket


class StoredFileNotFound(FileNotFoundError):
    """Indicate that an object does not exist in the configured storage."""


@dataclass(frozen=True)
class StoredFile:
    data: bytes
    content_type: str


class LocalFileStorage:
    """Store application files below a directory on the local filesystem."""

    def __init__(self, root_path: str) -> None:
        self.root_path = Path(root_path).expanduser().resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, object_name: str) -> Path:
        """Resolve an object name without allowing it to escape the root."""
        candidate = (self.root_path / object_name).resolve()
        if os.path.commonpath((self.root_path, candidate)) != str(self.root_path):
            raise ValueError("Storage object path escapes the configured root")
        return candidate

    def upload(
        self,
        object_name: str,
        file_object: BinaryIO,
        content_type: Optional[str] = None,
    ) -> None:
        """Write an uploaded stream atomically to the local storage root."""
        destination = self._resolve_path(object_name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=destination.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                shutil.copyfileobj(file_object, temporary_file)
            temporary_path.replace(destination)
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()

    def download(self, object_name: str) -> StoredFile:
        """Read a stored file and infer its content type from the extension."""
        path = self._resolve_path(object_name)
        try:
            data = path.read_bytes()
        except FileNotFoundError as error:
            raise StoredFileNotFound(object_name) from error
        content_type, _ = mimetypes.guess_type(path.name)
        return StoredFile(data, content_type or "application/octet-stream")

    def delete(self, object_name: str) -> None:
        """Delete a stored file and report missing objects consistently."""
        path = self._resolve_path(object_name)
        try:
            path.unlink()
        except FileNotFoundError as error:
            raise StoredFileNotFound(object_name) from error


class GoogleCloudStorage:
    """Store application files in a Google Cloud Storage bucket."""

    def __init__(self, bucket: Bucket) -> None:
        self.bucket = bucket

    def upload(
        self,
        object_name: str,
        file_object: BinaryIO,
        content_type: Optional[str] = None,
    ) -> None:
        """Upload a stream to Google Cloud Storage."""
        self.bucket.blob(object_name).upload_from_file(
            file_object,
            content_type=content_type,
        )

    def download(self, object_name: str) -> StoredFile:
        """Download an object and its content type from Google Cloud Storage."""
        blob = self.bucket.blob(object_name)
        try:
            data = blob.download_as_bytes()
        except NotFound as error:
            raise StoredFileNotFound(object_name) from error
        return StoredFile(data, blob.content_type or "application/octet-stream")

    def delete(self, object_name: str) -> None:
        """Delete an object from Google Cloud Storage."""
        try:
            self.bucket.blob(object_name).delete()
        except NotFound as error:
            raise StoredFileNotFound(object_name) from error
