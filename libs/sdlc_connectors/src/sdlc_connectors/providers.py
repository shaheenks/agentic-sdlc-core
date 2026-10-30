"""Provider adapters for user connections (version-01 M6): auth, token check, read-only calls.

Each connection (connections.yaml) is one provider + edition + API base URL:

  github     cloud: https://api.github.com            datacenter (GHE Server): https://<host>/api/v3
  bitbucket  cloud: https://api.bitbucket.org         datacenter: https://<host>[/<context>]
  jira | confluence | atlassian (Cloud: one site, both products)
             cloud: https://<site>.atlassian.net      datacenter: https://<host>[/<context>]

Auth: GitHub and every Data Center product use `Bearer <token>`; Bitbucket Cloud and Atlassian Cloud
API tokens use HTTP Basic with the account email. Verification checks the identity the provider
returns, not just the status (a misconfigured token can get a 200 as anonymous).

Results are untrusted content from the provider: tools return them as data, never as instructions.
Facts from provider documentation, not yet checked against live instances (version-01 §4.8).
"""

import base64
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote, urlsplit

from sdlc_config.model import ConnectionDef

from sdlc_connectors.errors import ConnectorError
from sdlc_connectors.http import HttpClient, HttpError
from sdlc_connectors.jira_text import adf_to_markdown, wiki_to_markdown
from sdlc_connectors.storage_format import storage_to_markdown

MAX_TEXT = 100_000  # characters of file/page/issue text returned by a tool

# Bitbucket Cloud answers 401 for every one of these, with no detail (Atlassian KB "Getting 401
# HTTP error ... Bitbucket Cloud REST APIs").
BITBUCKET_CLOUD_HINT = (
    "Bitbucket Cloud needs an Atlassian API token WITH SCOPES (id.atlassian.com > Security > "
    "Create API token with scopes > app Bitbucket) including read:user:bitbucket and "
    "read:repository:bitbucket, used with your Atlassian account email (not your Bitbucket "
    "username). Unscoped API tokens, app passwords and repository/workspace access tokens do "
    "not work here"
)


class TokenRejected(ConnectorError):
    """The provider did not accept the token (or it is not an acceptable token type)."""


@dataclass(frozen=True)
class Account:
    account: str  # provider login / account id
    display: str  # display name, for the Connections page
    expires_at: date | None = None  # when the provider reports it (GitHub)


def auth_header(conn: ConnectionDef, token: str, username: str | None) -> str:
    if conn.needs_username:
        if not username:
            raise TokenRejected(
                f"{conn.id}: this connection needs the account email with the token"
            )
        return "Basic " + base64.b64encode(f"{username}:{token}".encode()).decode()
    return f"Bearer {token}"


def client_for(conn: ConnectionDef, token: str, username: str | None, transport=None) -> HttpClient:
    """An HttpClient that may only reach the connection's own host, as the user."""
    host = urlsplit(conn.base_url).hostname or ""
    header = auth_header(conn, token, username)
    return HttpClient(
        (host,),
        auth_headers=lambda: {"Authorization": header},
        transport=transport,
        max_attempts=3,
        timeout=20.0,
    )


def _expiry(value: str | None) -> date | None:
    """GitHub-Authentication-Token-Expiration, e.g. '2026-12-31 12:00:00 UTC'."""
    if not value:
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2})", value.strip())
    return date.fromisoformat(match.group(1)) if match else None


def _get(client: HttpClient, url: str, **params) -> Any:
    try:
        return client.get_json(url, params=params or None)
    except HttpError as e:
        if e.status in (401, 403):
            raise TokenRejected(f"the provider refused the token ({e.status})") from None
        raise


# --- verification ---------------------------------------------------------------------------


def verify(conn: ConnectionDef, token: str, username: str | None, transport=None) -> Account:
    """Check the token against the provider's "who am I"; raise TokenRejected if unusable."""
    token = token.strip()
    if not token or any(c.isspace() for c in token):
        raise TokenRejected("empty or malformed token")
    if conn.provider == "github":
        if not token.startswith("github_pat_"):
            raise TokenRejected("use a fine-grained personal access token (github_pat_…)")
        with client_for(conn, token, username, transport) as client:
            try:
                response = client.request("GET", f"{conn.base_url}/user")
            except HttpError as e:
                if e.status in (401, 403):
                    raise TokenRejected(f"GitHub refused the token ({e.status})") from None
                raise
            me = response.json()
            expires = _expiry(response.headers.get("github-authentication-token-expiration"))
        return Account(
            str(me.get("login", "")), str(me.get("name") or me.get("login", "")), expires
        )
    with client_for(conn, token, username, transport) as client:
        if conn.provider == "bitbucket":
            if conn.edition == "cloud":
                try:
                    me = _get(client, f"{conn.base_url}/2.0/user")
                except TokenRejected as e:
                    raise TokenRejected(f"{e}. {BITBUCKET_CLOUD_HINT}") from None
                return Account(
                    str(me.get("account_id") or me.get("uuid", "")),
                    str(me.get("display_name") or me.get("nickname", "")),
                )
            response = client.request("GET", f"{conn.base_url}/plugins/servlet/applinks/whoami")
            name = response.text.strip()
            if response.status_code != 200 or not name:
                raise TokenRejected("Bitbucket did not identify the token's user")
            return Account(name, name)
        if conn.provider in ("jira", "atlassian"):
            version = "3" if conn.edition == "cloud" else "2"
            me = _get(client, f"{conn.base_url}/rest/api/{version}/myself")
            account = me.get("accountId") or me.get("key") or me.get("name")
            if not account:
                raise TokenRejected("Jira did not identify the token's user")
            return Account(str(account), str(me.get("displayName") or account))
        if conn.provider == "confluence":
            prefix = "/wiki" if conn.edition == "cloud" else ""
            me = _get(client, f"{conn.base_url}{prefix}/rest/api/user/current")
            if me.get("type") == "anonymous" or not (me.get("accountId") or me.get("username")):
                raise TokenRejected("Confluence treated the token as anonymous")
            account = me.get("accountId") or me.get("username")
            return Account(str(account), str(me.get("displayName") or account))
    raise TokenRejected(f"unknown provider {conn.provider}")


# --- read-only tool calls ---------------------------------------------------------------------


def _cut(text: str) -> tuple[str, bool]:
    return (text[:MAX_TEXT], True) if len(text) > MAX_TEXT else (text, False)


def _name(value: Any) -> str | None:
    return (value or {}).get("name") if isinstance(value, dict) else None


def jira_issue(client: HttpClient, conn: ConnectionDef, key: str) -> dict:
    if not re.fullmatch(r"[A-Z][A-Z0-9_]+-\d+", key):
        raise ValueError("an issue key looks like PAY-123")
    cloud = conn.edition == "cloud"
    fields = "summary,status,issuetype,priority,components,labels,description,resolution,security"
    body = _get(
        client, f"{conn.base_url}/rest/api/{'3' if cloud else '2'}/issue/{key}", fields=fields
    )
    f = body.get("fields") or {}
    description = f.get("description")
    text = (
        adf_to_markdown(description)
        if cloud and not isinstance(description, str)
        else (wiki_to_markdown(description))
    )
    text, truncated = _cut(text)
    return {
        "key": body.get("key", key),
        "url": f"{conn.base_url}/browse/{body.get('key', key)}",
        "summary": f.get("summary"),
        "type": _name(f.get("issuetype")),
        "status": _name(f.get("status")),
        "priority": _name(f.get("priority")),
        "resolution": _name(f.get("resolution")),
        "components": [c.get("name") for c in f.get("components") or []],
        "labels": f.get("labels") or [],
        "security_level": _name(f.get("security")),  # visible to you; mind who you share it with
        "description": text,
        "truncated": truncated,
    }


def confluence_page(client: HttpClient, conn: ConnectionDef, page_id: str) -> dict:
    if not page_id.isdigit():
        raise ValueError("a Confluence page id is a number")
    prefix = "/wiki" if conn.edition == "cloud" else ""
    body = _get(
        client,
        f"{conn.base_url}{prefix}/rest/api/content/{page_id}",
        expand="body.storage,space,version",
    )
    storage = ((body.get("body") or {}).get("storage") or {}).get("value", "")
    text, truncated = _cut(storage_to_markdown(storage))
    links = body.get("_links") or {}
    return {
        "id": str(body.get("id", page_id)),
        "title": body.get("title"),
        "space": (body.get("space") or {}).get("key"),
        "version": (body.get("version") or {}).get("number"),
        "url": (links.get("base") or f"{conn.base_url}{prefix}") + (links.get("webui") or ""),
        "content": text,
        "truncated": truncated,
    }


_REPO = re.compile(r"[A-Za-z0-9_.~-]+/[A-Za-z0-9_.-]+")
_SAFE_PATH = re.compile(r"[^\x00-\x1f]+")


def _check_repo_path(repo: str, path: str) -> str:
    if not _REPO.fullmatch(repo):
        raise ValueError("repo looks like owner/name")
    path = path.strip("/")
    if not path or not _SAFE_PATH.fullmatch(path) or ".." in path.split("/"):
        raise ValueError("invalid file path")
    return path


def _web_base(conn: ConnectionDef) -> str:
    """GitHub web host for links: api.github.com -> github.com, <ghe>/api/v3 -> <ghe>."""
    parts = urlsplit(conn.base_url)
    if conn.edition == "cloud":
        return "https://github.com"
    return f"https://{parts.netloc}"


def github_file(client: HttpClient, conn: ConnectionDef, repo: str, path: str, ref: str) -> dict:
    path = _check_repo_path(repo, path)
    params = {"ref": ref} if ref else None
    try:
        response = client.request(
            "GET",
            f"{conn.base_url}/repos/{repo}/contents/{quote(path)}",
            params=params,
            headers={"Accept": "application/vnd.github.raw+json"},
        )
    except HttpError as e:
        if e.status in (401, 403):
            raise TokenRejected(f"GitHub refused the token ({e.status})") from None
        raise
    text, truncated = _cut(response.text)
    return {
        "repo": repo,
        "path": path,
        "ref": ref or "default branch",
        "url": f"{_web_base(conn)}/{repo}/blob/{quote(ref or 'HEAD')}/{quote(path)}",
        "content": text,
        "truncated": truncated,
    }


def bitbucket_file(client: HttpClient, conn: ConnectionDef, repo: str, path: str, ref: str) -> dict:
    path = _check_repo_path(repo, path)
    owner, name = repo.split("/", 1)
    if conn.edition == "cloud":
        if not ref:
            meta = _get(client, f"{conn.base_url}/2.0/repositories/{owner}/{name}")
            ref = ((meta.get("mainbranch") or {}).get("name")) or "main"
        src = f"{quote(ref, safe='')}/{quote(path)}"
        url = f"{conn.base_url}/2.0/repositories/{owner}/{name}/src/{src}"
        web = f"https://bitbucket.org/{owner}/{name}/src/{quote(ref, safe='')}/{quote(path)}"
        params = None
    else:
        url = f"{conn.base_url}/rest/api/latest/projects/{owner}/repos/{name}/raw/{quote(path)}"
        web = f"{conn.base_url}/projects/{owner.upper()}/repos/{name}/browse/{quote(path)}"
        params = {"at": ref} if ref else None
        if ref:
            web += f"?at={quote(ref, safe='')}"
    try:
        response = client.request("GET", url, params=params)
    except HttpError as e:
        if e.status in (401, 403):
            raise TokenRejected(f"Bitbucket refused the token ({e.status})") from None
        raise
    text, truncated = _cut(response.text)
    return {
        "repo": repo,
        "path": path,
        "ref": ref or "default branch",
        "url": web,
        "content": text,
        "truncated": truncated,
    }


def today() -> date:
    return datetime.now(UTC).date()
