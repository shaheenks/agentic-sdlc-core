"""Where bundles are kept: a local folder, or the environment's configuration bucket."""

import os
from pathlib import Path
from typing import Protocol

ACTIVE = "active.json"


def bundle_name(version: str) -> str:
    return f"bundles/{version}.json"


class Source(Protocol):
    def read_active(self) -> tuple[bytes, str]:
        """The content of active.json and a stamp that changes whenever it is rewritten."""
        ...

    def read(self, name: str) -> bytes: ...

    def write(self, name: str, data: bytes, *, if_absent: bool = False) -> None: ...

    def exists(self, name: str) -> bool: ...

    def describe(self) -> str: ...


class DirSource:
    """A local folder: the `local` profile, and tests."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def read_active(self) -> tuple[bytes, str]:
        path = self.root / ACTIVE
        stat = path.stat()
        return path.read_bytes(), f"{stat.st_mtime_ns}-{stat.st_size}"

    def read(self, name: str) -> bytes:
        return (self.root / name).read_bytes()

    def write(self, name: str, data: bytes, *, if_absent: bool = False) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if if_absent and path.exists():
            return
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)

    def exists(self, name: str) -> bool:
        return (self.root / name).is_file()

    def describe(self) -> str:
        return str(self.root)


class GcsSource:
    """The configuration bucket, read with the service's own credentials (Application Default Credentials).
    The stamp of active.json is its object generation."""

    def __init__(self, bucket: str, prefix: str = "", client=None) -> None:
        if client is None:
            from google.cloud import storage

            client = storage.Client()
        self._bucket = client.bucket(bucket)
        self.bucket_name = bucket
        self.prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""

    def _blob(self, name: str):
        return self._bucket.blob(self.prefix + name)

    def read_active(self) -> tuple[bytes, str]:
        blob = self._bucket.get_blob(self.prefix + ACTIVE)
        if blob is None:
            raise FileNotFoundError(f"gs://{self.bucket_name}/{self.prefix}{ACTIVE}")
        return blob.download_as_bytes(if_generation_match=blob.generation), str(blob.generation)

    def read(self, name: str) -> bytes:
        return self._blob(name).download_as_bytes()

    def write(self, name: str, data: bytes, *, if_absent: bool = False) -> None:
        from google.api_core.exceptions import PreconditionFailed

        try:
            self._blob(name).upload_from_string(
                data, content_type="application/json", if_generation_match=0 if if_absent else None
            )
        except PreconditionFailed:
            if not if_absent:
                raise

    def exists(self, name: str) -> bool:
        return self._blob(name).exists()

    def describe(self) -> str:
        return f"gs://{self.bucket_name}/{self.prefix}"


def source_from_url(url: str) -> Source:
    """`gs://bucket[/prefix]` or a folder path."""
    if url.startswith("gs://"):
        bucket, _, prefix = url.removeprefix("gs://").partition("/")
        return GcsSource(bucket, prefix)
    return DirSource(Path(url))
