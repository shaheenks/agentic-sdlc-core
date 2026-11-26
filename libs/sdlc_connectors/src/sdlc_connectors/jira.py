"""Jira, cloud and Data Center editions.

- Cloud: REST API v3, basic authentication with the Atlassian account email and an API token; descriptions are
  Atlassian Document Format, converted from and to plain text with paragraphs.
- Data Center: REST API v2 with a personal access token (bearer); descriptions are text.
"""

import base64
import re
from dataclasses import dataclass
from typing import Any

import httpx

from sdlc_connectors.base import ConnectorError, Credential, Http

KEY = re.compile(r"^[A-Z][A-Z0-9_]{0,19}-[1-9][0-9]{0,9}$")
CLOUD, DATA_CENTER = "cloud", "data_center"

LABEL = re.compile(r"^[A-Za-z0-9_.-]{1,50}$")
FIELD_ID = re.compile(r"^customfield_[0-9]{1,8}$")


@dataclass(frozen=True)
class Issue:
    key: str
    summary: str
    status: str
    issue_type: str
    description: str
    parent: str | None
    url: str

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "summary": self.summary,
            "status": self.status,
            "issue_type": self.issue_type,
            "description": self.description,
            "parent": self.parent,
            "url": self.url,
        }


def adf_to_text(node: Any) -> str:
    """Plain text of an Atlassian Document Format node: blocks on their own lines, list items with a dash."""
    if not isinstance(node, dict):
        return ""
    kind = node.get("type")
    if kind == "text":
        return str(node.get("text", ""))
    if kind == "hardBreak":
        return "\n"
    inner = "".join(adf_to_text(c) for c in node.get("content") or ())
    if kind == "listItem":
        return "- " + inner.strip() + "\n"
    if kind in ("paragraph", "heading", "codeBlock", "blockquote", "bulletList", "orderedList", "rule"):
        return inner.rstrip("\n") + "\n\n"
    return inner


def text_to_adf(text: str) -> dict[str, Any]:
    """A document of one paragraph per block of text (blank lines separate blocks)."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text or "") if b.strip()]
    content = []
    for block in blocks:
        parts: list[dict[str, Any]] = []
        for i, line in enumerate(block.split("\n")):
            if i:
                parts.append({"type": "hardBreak"})
            if line:
                parts.append({"type": "text", "text": line})
        content.append({"type": "paragraph", "content": parts})
    return {"type": "doc", "version": 1, "content": content}


class Jira:
    def __init__(self, base_url: str, edition: str, credential: Credential, client: httpx.Client | None = None):
        if edition == CLOUD:
            if not credential.account:
                raise ConnectorError("invalid", "a Jira Cloud connection needs the account email")
            basic = base64.b64encode(f"{credential.account}:{credential.token}".encode()).decode()
            headers, self.api = {"Authorization": f"Basic {basic}"}, "/rest/api/3"
        elif edition == DATA_CENTER:
            headers, self.api = {"Authorization": f"Bearer {credential.token}"}, "/rest/api/2"
        else:
            raise ValueError(f"unknown Jira edition {edition!r}")
        self.edition = edition
        self.base_url = base_url.rstrip("/")
        self.http = Http(self.base_url, headers, "Jira", client)

    def _description(self, value: Any) -> str:
        return adf_to_text(value).strip() if self.edition == CLOUD else str(value or "")

    def _issue(self, raw: dict[str, Any]) -> Issue:
        fields = raw.get("fields") or {}
        return Issue(
            key=raw["key"],
            summary=fields.get("summary") or "",
            status=((fields.get("status") or {}).get("name")) or "",
            issue_type=((fields.get("issuetype") or {}).get("name")) or "",
            description=self._description(fields.get("description")),
            parent=((fields.get("parent") or {}).get("key")),
            url=f"{self.base_url}/browse/{raw['key']}",
        )

    def whoami(self) -> dict[str, Any]:
        me = self.http.request("GET", f"{self.api}/myself")
        return {
            "account": me.get("emailAddress") or me.get("name") or me.get("accountId"),
            "name": me.get("displayName"),
        }

    def get_issue(self, key: str) -> Issue:
        if not KEY.match(key):
            raise ConnectorError("invalid", "not a Jira issue key")
        fields = "summary,status,issuetype,description,parent"
        return self._issue(self.http.request("GET", f"{self.api}/issue/{key}", params={"fields": fields}))

    def search(self, jql: str, limit: int = 20) -> list[Issue]:
        body = {"jql": jql, "maxResults": limit, "fields": ["summary", "status", "issuetype", "description", "parent"]}
        path = f"{self.api}/search/jql" if self.edition == CLOUD else f"{self.api}/search"
        found = self.http.request("POST", path, json=body)
        return [self._issue(i) for i in (found or {}).get("issues") or ()]

    def children(self, key: str, project: str) -> list[Issue]:
        """The issues whose parent is `key` (stories of a feature), within one project."""
        return self.search(f'project = "{project}" AND parent = {key} ORDER BY key', limit=100)

    def create_issue(
        self,
        project: str,
        issue_type: str,
        summary: str,
        description: str,
        parent: str | None = None,
        labels: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Issue:
        fields: dict[str, Any] = {
            "project": {"key": project},
            "issuetype": {"name": issue_type},
            "summary": summary[:250],
            "description": text_to_adf(description) if self.edition == CLOUD else description,
        }
        if parent:
            fields["parent"] = {"key": parent}
        if labels:
            fields["labels"] = [label for label in labels if LABEL.match(label)]
        fields |= {k: v for k, v in (extra or {}).items() if FIELD_ID.match(k)}
        created = self.http.request("POST", f"{self.api}/issue", json={"fields": fields})
        return self.get_issue(created["key"])

    def field_id(self, names: tuple[str, ...]) -> str | None:
        """The ID of the first field whose name is one of `names` (custom fields such as story points differ per
        site and project), or None."""
        wanted = [n.lower() for n in names]
        found = {
            str(f.get("name", "")).lower(): str(f.get("id", ""))
            for f in self.http.request("GET", f"{self.api}/field") or ()
            if isinstance(f, dict)
        }
        return next((found[n] for n in wanted if n in found and FIELD_ID.match(found[n])), None)

    def link_issues(self, outward: str, inward: str, link_type: str = "Relates") -> None:
        body = {"type": {"name": link_type}, "outwardIssue": {"key": outward}, "inwardIssue": {"key": inward}}
        self.http.request("POST", f"{self.api}/issueLink", json=body)

    def remote_links(self, key: str) -> list[dict[str, str]]:
        """The issue's links to web pages: [{url, title}]."""
        found = self.http.request("GET", f"{self.api}/issue/{key}/remotelink") or []
        return [
            {"url": (link.get("object") or {}).get("url", ""), "title": (link.get("object") or {}).get("title", "")}
            for link in found
            if isinstance(link, dict)
        ]

    def add_web_link(self, key: str, url: str, title: str) -> None:
        """A link from the issue to a web page (a pull request)."""
        body = {"globalId": url, "object": {"url": url, "title": title[:250]}}
        self.http.request("POST", f"{self.api}/issue/{key}/remotelink", json=body)
