"""jira sources (version-01 M4): the issues a JQL query selects, Cloud or Data Center.

  location: https://<site>.atlassian.net (Cloud) | https://<host>[/<context>] (Data Center)
  jql: "project = PAY AND issuetype in (Incident, Bug)"      fields: [summary, description, ...]

- Cloud: REST v3 enhanced search (`/rest/api/3/search/jql`, nextPageToken; rich text is ADF).
  Data Center: REST v2 (`/rest/api/2/search`, startAt; rich text is wiki markup).
- Every run lists all matching issues with only `updated` and `security` (cheap), so deletions and
  issues that gained an issue security level are always found; full fields are fetched only for
  issues whose `updated` changed since the cursor (or all, without a cursor / with --force).
- Native restrictions (version-01 §2.6): an issue with an issue security level is never ingested
  and a stored copy is deleted.
- One Markdown document per issue, id = issue key (`PAY-123`), title `PAY-123: <summary>`, linked
  to `<location>/browse/PAY-123`. People fields (assignee, reporter, comment authors) are never
  included.
"""

from collections.abc import Callable, Iterator, Mapping
from typing import Any

from sdlc_connectors.http import HttpClient
from sdlc_connectors.jira_text import adf_to_markdown, wiki_to_markdown

from sdlc_loaders.atlassian import atlassian_client
from sdlc_loaders.base import MARKDOWN, Loader, LoaderContext, SourceItem
from sdlc_loaders.files import _source_file

DEFAULT_FIELDS = (
    "summary",
    "description",
    "issuetype",
    "status",
    "priority",
    "components",
    "labels",
    "issuelinks",
)
FIELD_CHOICES = (*DEFAULT_FIELDS, "resolution", "fixVersions", "comment")
PAGE_SIZE = 100
BATCH = 50  # keys per "key in (...)" fetch


def _name(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("name") or value.get("value") or "")
    return str(value or "")


class JiraLoader(Loader):
    incremental = True

    def __init__(
        self,
        location: str,
        edition: str,
        jql: str,
        fields: tuple[str, ...],
        client_factory: Callable[[], HttpClient],
    ) -> None:
        super().__init__()
        self.location, self.edition = location.rstrip("/"), edition
        self.jql, self.fields = jql, fields or DEFAULT_FIELDS
        self._client_factory = client_factory
        self._ids: set[str] = set()

    @property
    def cloud(self) -> bool:
        return self.edition == "cloud"

    def _rich(self, value: Any) -> str:
        if self.cloud and not isinstance(value, str):
            return adf_to_markdown(value)
        return wiki_to_markdown(value)

    # --- REST ---------------------------------------------------------------------------------

    def _search(self, client: HttpClient, jql: str, fields: list[str]) -> Iterator[dict]:
        params: dict[str, Any] = {"jql": jql, "fields": ",".join(fields), "maxResults": PAGE_SIZE}
        if self.cloud:
            url = f"{self.location}/rest/api/3/search/jql"
            while True:
                body = client.get_json(url, params=params)
                yield from body.get("issues", [])
                token = body.get("nextPageToken")
                if not token or body.get("isLast"):
                    return
                params = {**params, "nextPageToken": token}
        url = f"{self.location}/rest/api/2/search"
        start = 0
        while True:
            body = client.get_json(url, params={**params, "startAt": start})
            issues = body.get("issues", [])
            yield from issues
            start += len(issues)
            if not issues or start >= int(body.get("total", 0)):
                return

    # --- items --------------------------------------------------------------------------------

    def _selection(self) -> dict[str, Any]:
        return {"location": self.location, "jql": self.jql, "fields": list(self.fields)}

    def items(self, cursor: Mapping[str, Any] | None = None) -> Iterator[SourceItem]:
        selection = self._selection()
        known: dict[str, str] = {}
        if cursor and all(cursor.get(k) == v for k, v in selection.items()):
            known = dict(cursor.get("versions", {}))
        versions: dict[str, str] = {}
        changed: list[str] = []
        restricted = 0
        client = self._client_factory()
        try:
            for issue in self._search(client, self.jql, ["updated", "security"]):
                key = issue["key"]
                fields = issue.get("fields") or {}
                if fields.get("security"):  # an issue security level: never ingested
                    restricted += 1
                    yield SourceItem(path=key, text="", content_hash="", restricted=True)
                    continue
                versions[key] = str(fields.get("updated", ""))
                if known.get(key) != versions[key]:
                    changed.append(key)
            wanted = sorted({*self.fields, "summary", "security"})
            for i in range(0, len(changed), BATCH):
                keys = changed[i : i + BATCH]
                for issue in self._search(client, f"key in ({','.join(keys)})", wanted):
                    if (issue.get("fields") or {}).get("security"):  # changed since the listing
                        versions.pop(issue["key"], None)
                        restricted += 1
                        yield SourceItem(
                            path=issue["key"], text="", content_hash="", restricted=True
                        )
                        continue
                    item = self._issue_item(issue)
                    if item is not None:
                        yield item
        finally:
            client.close()
        self._ids = set(versions)
        self.details.update(issues=len(versions), restricted=restricted)
        self.cursor = {**selection, "versions": versions}

    def _issue_item(self, issue: Mapping[str, Any]) -> SourceItem | None:
        key, f = issue["key"], issue.get("fields") or {}
        summary = str(f.get("summary") or "").strip()
        title = f"{key}: {summary}" if summary else key
        lines = [f"# {title}", ""]
        facts = [
            (label, _name(f.get(field)))
            for label, field in (
                ("Type", "issuetype"),
                ("Status", "status"),
                ("Priority", "priority"),
                ("Resolution", "resolution"),
            )
            if field in self.fields and f.get(field)
        ]
        if facts:
            lines.append(" · ".join(f"{label}: {value}" for label, value in facts))
        for label, field in (("Components", "components"), ("Fix versions", "fixVersions")):
            if field in self.fields and f.get(field):
                lines.append(f"{label}: " + ", ".join(_name(v) for v in f[field]))
        if "labels" in self.fields and f.get("labels"):
            lines.append("Labels: " + ", ".join(f["labels"]))
        if "issuelinks" in self.fields and f.get("issuelinks"):
            links = []
            for link in f["issuelinks"]:
                kind = link.get("type") or {}
                if link.get("outwardIssue"):
                    links.append(
                        f"{kind.get('outward', 'relates to')} {link['outwardIssue']['key']}"
                    )
                elif link.get("inwardIssue"):
                    links.append(f"{kind.get('inward', 'relates to')} {link['inwardIssue']['key']}")
            if links:
                lines.append("Links: " + "; ".join(links))
        lines.append("")
        if "description" in self.fields and f.get("description"):
            lines += ["## Description", "", self._rich(f["description"]).strip(), ""]
        if "comment" in self.fields:
            comments = (f.get("comment") or {}).get("comments") or []
            if comments:
                lines += ["## Comments", ""]
                for c in comments:
                    when = str(c.get("created", ""))[:10]
                    lines += [
                        f"### Comment {when}".rstrip(),
                        "",
                        self._rich(c.get("body")).strip(),
                        "",
                    ]
        item = _source_file(key, ("\n".join(lines).strip() + "\n").encode("utf-8"))
        if item is None:  # over the text size limit: listed (not deleted), not indexed
            self.details["too_large"] = self.details.get("too_large", 0) + 1
            return None
        return SourceItem(
            path=key,
            text=item.text,
            content_hash=item.content_hash,
            media_type=MARKDOWN,
            title=title,
            url=f"{self.location}/browse/{key}",
        )

    def all_ids(self) -> set[str]:
        return set(self._ids)


def jira(source, ctx: LoaderContext) -> Loader:
    options = source.options
    return JiraLoader(
        source.location,
        options["edition"],
        options["jql"],
        tuple(options.get("fields", ())),
        atlassian_client(source, ctx),
    )
