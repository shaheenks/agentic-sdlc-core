"""confluence sources (version-01 M3): the pages of one space, Cloud or Data Center.

  location: https://<site>.atlassian.net/wiki  (Cloud) | https://<host>[/<context>]  (Data Center)
  space: PAY            cql: "label = runbook" (optional narrowing)       attachments: [pdf]

- One API for both editions: REST v1 content search with CQL (`/rest/api/content/search`).
- Every run lists all selected pages with version, ancestors and read restrictions (no bodies), so
  deletions and newly restricted pages are always found; bodies are fetched only for pages whose
  version changed since the cursor (or all, without a cursor / with --force).
- Native restrictions (version-01 §2.6): a page with read restrictions on itself or any ancestor
  is never ingested, and a stored copy is deleted. Restrictions that cannot be read count as
  restricted (fail closed). Attachments follow their page.
- Item ids: `<SPACE>/<page id>`; PDF attachments `<SPACE>/<page id>/attachments/<attachment id>`.
  Pages become Markdown (`# Title`, the ancestor path, then the body) for the Markdown chunker.
"""

from collections.abc import Callable, Iterator, Mapping
from typing import Any
from urllib.parse import urljoin

from sdlc_connectors.http import HttpClient
from sdlc_connectors.storage_format import storage_to_markdown

from sdlc_loaders.atlassian import atlassian_client
from sdlc_loaders.base import MARKDOWN, Loader, LoaderContext, SourceItem
from sdlc_loaders.files import MAX_PDF_BYTES, _source_file

PAGE_LIMIT = 50
RESTRICTIONS = "restrictions.read.restrictions.user,restrictions.read.restrictions.group"


def _cql_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def read_restricted(content: Mapping[str, Any]) -> bool | None:
    """True if read restrictions name any user or group; None if they were not returned."""
    try:
        read = content["restrictions"]["read"]["restrictions"]
    except (KeyError, TypeError):
        return None
    for kind in ("user", "group"):
        entry = read.get(kind) or {}
        if entry.get("results") or entry.get("size"):
            return True
    return False


class ConfluenceLoader(Loader):
    incremental = True

    def __init__(
        self,
        location: str,
        space: str,
        cql: str | None,
        attachments: tuple[str, ...],
        client_factory: Callable[[], HttpClient],
    ) -> None:
        super().__init__()
        self.location = location.rstrip("/")
        self.space, self.cql, self.attachments = space, cql, attachments
        self._client_factory = client_factory
        self._ids: set[str] = set()
        self._restricted_cache: dict[str, bool] = {}

    # --- REST ---------------------------------------------------------------------------------

    def _base(self, body: Mapping[str, Any]) -> str:
        return (body.get("_links") or {}).get("base") or self.location

    def _search(self, client: HttpClient, cql: str, expand: str) -> Iterator[tuple[dict, str]]:
        url: str | None = f"{self.location}/rest/api/content/search"
        params: dict[str, Any] | None = {"cql": cql, "limit": PAGE_LIMIT, "expand": expand}
        while url:
            body = client.get_json(url, params=params)
            base = self._base(body)
            for result in body.get("results", []):
                yield result, base
            following = (body.get("_links") or {}).get("next")
            url, params = (base + following if following else None), None

    def _ancestor_restricted(self, client: HttpClient, ancestor_id: str) -> bool:
        if ancestor_id not in self._restricted_cache:
            body = client.get_json(
                f"{self.location}/rest/api/content/{ancestor_id}", params={"expand": RESTRICTIONS}
            )
            restricted = read_restricted(body)
            self._restricted_cache[ancestor_id] = restricted is not False  # unknown = restricted
        return self._restricted_cache[ancestor_id]

    def _restricted(self, client: HttpClient, page: Mapping[str, Any]) -> bool:
        own = read_restricted(page)
        if own is None:  # expansion not honoured: ask for this page directly
            own = self._ancestor_restricted(client, str(page["id"]))
        if own:
            return True
        return any(
            self._ancestor_restricted(client, str(a["id"])) for a in page.get("ancestors") or []
        )

    # --- items --------------------------------------------------------------------------------

    def _selection(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "space": self.space,
            "cql": self.cql,
            "attachments": list(self.attachments),
        }

    def items(self, cursor: Mapping[str, Any] | None = None) -> Iterator[SourceItem]:
        selection = self._selection()
        known: dict[str, str] = {}
        if cursor and all(cursor.get(k) == v for k, v in selection.items()):
            known = dict(cursor.get("versions", {}))
        versions: dict[str, str] = {}
        allowed_pages: dict[str, str] = {}  # page id -> page url (not restricted)
        restricted_paths = 0
        client = self._client_factory()
        try:
            cql = f"space = {_cql_quote(self.space)} AND type = page"
            if self.cql:
                cql += f" AND ({self.cql})"
            expand = f"version,ancestors,{RESTRICTIONS}"
            for page, base in self._search(client, cql, expand):
                page_id = str(page["id"])
                path = f"{self.space}/{page_id}"
                if self._restricted(client, page):
                    restricted_paths += 1
                    yield SourceItem(path=path, text="", content_hash="", restricted=True)
                    continue
                version = str((page.get("version") or {}).get("number", ""))
                url = base + ((page.get("_links") or {}).get("webui") or "")
                allowed_pages[page_id] = url
                versions[path] = version
                if known.get(path) == version:
                    continue
                item = self._page_item(client, page, path, url)
                if item is not None:
                    yield item
            if "pdf" in self.attachments:
                yield from self._attachments(client, allowed_pages, known, versions)
        finally:
            client.close()
        self._ids = set(versions)
        self.details.update(pages=len(allowed_pages), restricted=restricted_paths)
        self.cursor = {**selection, "versions": versions}

    def _page_item(self, client, page, path, url) -> SourceItem | None:
        body = client.get_json(
            f"{self.location}/rest/api/content/{page['id']}", params={"expand": "body.storage"}
        )
        storage = ((body.get("body") or {}).get("storage") or {}).get("value", "")
        title = page.get("title") or body.get("title") or path
        trail = [a.get("title", "") for a in page.get("ancestors") or [] if a.get("title")]
        parts = [f"# {title}", ""]
        if trail:
            parts += ["Path: " + " > ".join([*trail, title]), ""]
        text = "\n".join(parts) + "\n" + storage_to_markdown(storage)
        item = _source_file(path, text.encode("utf-8"))
        if item is None:  # over the text size limit: listed (so not deleted), not indexed
            self.details["too_large"] = self.details.get("too_large", 0) + 1
            return None
        return SourceItem(
            path=path,
            text=item.text,
            content_hash=item.content_hash,
            media_type=MARKDOWN,
            title=title,
            url=url,
        )

    def _attachments(self, client, allowed_pages, known, versions) -> Iterator[SourceItem]:
        cql = f"space = {_cql_quote(self.space)} AND type = attachment"
        for att, base in self._search(client, cql, "version,container"):
            container = str((att.get("container") or {}).get("id", ""))
            if container not in allowed_pages:  # restricted page, or not selected by cql
                continue
            title = att.get("title") or ""
            ext = att.get("extensions") or {}
            if ext.get("mediaType") != "application/pdf" and not title.lower().endswith(".pdf"):
                continue
            if int(ext.get("fileSize") or 0) > MAX_PDF_BYTES:
                continue
            path = f"{self.space}/{container}/attachments/{att['id']}"
            version = str((att.get("version") or {}).get("number", ""))
            versions[path] = version
            if known.get(path) == version:
                continue
            download = (att.get("_links") or {}).get("download")
            if not download:
                continue
            raw = client.request("GET", urljoin(base + "/", download.lstrip("/"))).content
            item = _source_file(title, raw)
            if item is None or not item.is_pdf:
                continue
            yield SourceItem(
                path=path,
                text="",
                content_hash=item.content_hash,
                media_type=item.media_type,
                raw=item.raw,
                title=title,
                url=allowed_pages[container],
            )

    def all_ids(self) -> set[str]:
        return set(self._ids)


def confluence(source, ctx: LoaderContext) -> Loader:
    options = source.options
    return ConfluenceLoader(
        source.location,
        options["space"],
        options.get("cql"),
        tuple(options.get("attachments", ())),
        atlassian_client(source, ctx),
    )
