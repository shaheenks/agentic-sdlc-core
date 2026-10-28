"""gcs sources (version-01 M2): objects under a Cloud Storage prefix.

  location: gs://<bucket>/<prefix>/      include/exclude match names relative to the prefix

- Access: the GCS JSON API with Application Default Credentials (the ingest service identity on
  Cloud Run, gcloud ADC locally), read-only scope. No keys and no `spec.credentials`: grant the
  identity roles/storage.objectViewer on that bucket only.
- Unchanged objects are not downloaded: the cursor records each object's generation (a new
  generation = new content). A run downloads only new or changed objects; the full listing
  (`all_ids`) finds deletions. --force (no cursor) downloads everything.
- Objects above the text/PDF size limits are skipped from the listing's size, before download.
- Each item links to the object in the Cloud Console's authenticated browser (`url`).
"""

from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sdlc_loaders.base import Loader, LoaderError, SourceItem
from sdlc_loaders.files import _selected, _source_file, _too_large
from sdlc_loaders.http import HttpClient

API = "https://storage.googleapis.com"
API_HOSTS = ("storage.googleapis.com",)  # fixed endpoint: no config can redirect it
BROWSER = "https://storage.cloud.google.com"
READ_ONLY_SCOPE = "https://www.googleapis.com/auth/devstorage.read_only"
PAGE_SIZE = 1000


def parse_location(location: str) -> tuple[str, str]:
    """gs://bucket/some/prefix/ -> ("bucket", "some/prefix/"). The prefix is "" or ends with /."""
    if not location.startswith("gs://"):
        raise ValueError(f"not a gs:// location: {location}")
    bucket, _, prefix = location[len("gs://") :].partition("/")
    if not bucket:
        raise ValueError(f"no bucket in {location}")
    prefix = prefix.lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return bucket, prefix


class GoogleToken:
    """Bearer tokens from ADC, refreshed when expired or after a 401 (`invalidate`)."""

    def __init__(self, scopes: tuple[str, ...] = (READ_ONLY_SCOPE,)) -> None:
        self._scopes, self._credentials, self._request = scopes, None, None

    def headers(self) -> dict[str, str]:
        import google.auth
        import google.auth.exceptions
        import google.auth.transport.requests

        if self._credentials is None:
            try:
                self._credentials, _ = google.auth.default(scopes=list(self._scopes))
            except google.auth.exceptions.DefaultCredentialsError as e:
                raise LoaderError(f"no Google credentials (ADC): {e}") from None
            self._request = google.auth.transport.requests.Request()
        if not self._credentials.valid:
            self._credentials.refresh(self._request)
        return {"Authorization": f"Bearer {self._credentials.token}"}

    def invalidate(self) -> None:
        if self._credentials is not None:
            self._credentials.expiry = None  # force a refresh on the next request
            self._credentials.token = None


class GcsLoader(Loader):
    incremental = True

    def __init__(
        self,
        location: str,
        include: tuple[str, ...],
        exclude: tuple[str, ...],
        *,
        client_factory: Callable[[], HttpClient] | None = None,
    ) -> None:
        super().__init__()
        self.location, self.include, self.exclude = location, include, exclude
        self.bucket, self.prefix = parse_location(location)
        self._client_factory = client_factory or self._default_client
        self._ids: set[str] = set()

    @staticmethod
    def _default_client() -> HttpClient:
        token = GoogleToken()
        return HttpClient(API_HOSTS, auth_headers=token.headers, on_unauthorized=token.invalidate)

    def _objects(self, client: HttpClient) -> Iterator[dict]:
        url = f"{API}/storage/v1/b/{quote(self.bucket, safe='')}/o"
        params: dict[str, Any] = {
            "prefix": self.prefix,
            "maxResults": PAGE_SIZE,
            "fields": "items(name,generation,size,updated),nextPageToken",
        }
        while True:
            page = client.get_json(url, params=params)
            yield from page.get("items", [])
            token = page.get("nextPageToken")
            if not token:
                return
            params = {**params, "pageToken": token}

    def items(self, cursor: Mapping[str, Any] | None = None) -> Iterator[SourceItem]:
        known = dict((cursor or {}).get("generations", {}))
        if (cursor or {}).get("location") != self.location:
            known = {}  # a different bucket/prefix: read everything
        generations: dict[str, str] = {}
        client = self._client_factory()
        try:
            listing = list(self._objects(client))
            for obj in listing:
                name = obj.get("name", "")
                rel = name[len(self.prefix) :]
                if not rel or name.endswith("/") or not _selected(rel, self.include, self.exclude):
                    continue
                if _too_large(rel, int(obj.get("size", 0))):
                    continue
                generation = str(obj.get("generation", ""))
                generations[rel] = generation
                if known.get(rel) == generation:
                    continue  # unchanged: not downloaded
                raw = client.request(
                    "GET",
                    f"{API}/storage/v1/b/{quote(self.bucket, safe='')}/o/{quote(name, safe='')}",
                    params={"alt": "media", "generation": generation},
                ).content
                item = _source_file(rel, raw)
                if item is None:
                    continue  # binary or not UTF-8 (still listed, so not deleted)
                yield SourceItem(
                    path=item.path,
                    text=item.text,
                    content_hash=item.content_hash,
                    media_type=item.media_type,
                    raw=item.raw,
                    url=f"{BROWSER}/{quote(self.bucket, safe='')}/{quote(name, safe='/')}",
                )
        finally:
            client.close()
        self._ids = set(generations)
        self.details.update(objects=len(generations))
        self.cursor = {"location": self.location, "generations": generations}

    def all_ids(self) -> set[str]:
        return set(self._ids)


def gcs(source, repo_root: Path, cache_root: Path, secrets=None) -> Loader:
    return GcsLoader(source.location, source.include, source.exclude)
