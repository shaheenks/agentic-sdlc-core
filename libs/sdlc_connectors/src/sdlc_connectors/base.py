"""What every adapter shares: one HTTP client per call, errors mapped to a small set of codes, and nothing of the
credential, the request or the response body in an error message."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

TIMEOUT = 20.0


class ConnectorError(Exception):
    """A downstream call failed. `code` is one of: unauthorized (the connection does not sign in), forbidden,
    not_found, conflict, invalid (the system refused the request), unavailable."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Credential:
    """A user's (or the system's) connection to one system. `account` is the sign-in name where the edition needs
    one (Jira Cloud: the Atlassian account email; Bitbucket Cloud app passwords: the username)."""

    token: str
    account: str | None = None

    def __repr__(self) -> str:  # never print the token
        return f"Credential(account={self.account!r})"


_STATUS = {401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict", 422: "invalid", 400: "invalid"}


FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,40}$")


def _rejected_fields(response: httpx.Response) -> str:
    """The names of the fields a rejected request got wrong (Jira's `errors`, GitHub's `errors[].field`), never
    their values or any other part of the answer: enough to tell which setting to fix."""
    try:
        body = response.json()
    except ValueError:
        return ""
    names: list[str] = []
    if isinstance(body, dict):
        errors = body.get("errors")
        if isinstance(errors, dict):
            names = [k for k in errors if isinstance(k, str)]
        elif isinstance(errors, list):
            names = [e.get("field") for e in errors if isinstance(e, dict) and isinstance(e.get("field"), str)]
    names = sorted({n for n in names if FIELD.match(n)})[:5]
    return f": {', '.join(names)}" if names else ""


class Http:
    def __init__(self, base_url: str, headers: Mapping[str, str], system: str, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Accept": "application/json", **headers}
        self.system = system
        self.client = client or httpx.Client(timeout=TIMEOUT)

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, str] | None = None,
        files: Mapping[str, Any] | None = None,
    ) -> Any:
        """One call. A form (`data`) or multipart body (`files`) is sent without the JSON Accept header."""
        headers = (
            self.headers if data is None and files is None else {k: v for k, v in self.headers.items() if k != "Accept"}
        )
        try:
            response = self.client.request(
                method, f"{self.base_url}{path}", json=json, params=params, data=data, files=files, headers=headers
            )
        except httpx.HTTPError as exc:
            raise ConnectorError("unavailable", f"{self.system} did not answer") from exc
        if response.status_code >= 400:
            code = _STATUS.get(response.status_code, "unavailable")
            fields = _rejected_fields(response) if code == "invalid" else ""
            raise ConnectorError(code, f"{self.system} answered {response.status_code} ({code}{fields})")
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def download(self, path: str, max_bytes: int) -> bytes:
        """A file's bytes, following redirects (GitHub's archives redirect to a signed download URL, and httpx drops
        the Authorization header when a redirect leaves the host). Refused beyond `max_bytes`."""
        headers = {k: v for k, v in self.headers.items() if k != "Accept"}
        try:
            with self.client.stream(
                "GET", f"{self.base_url}{path}", headers=headers, follow_redirects=True, timeout=120
            ) as response:
                if response.status_code >= 400:
                    code = _STATUS.get(response.status_code, "unavailable")
                    raise ConnectorError(code, f"{self.system} answered {response.status_code} ({code})")
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ConnectorError("invalid", f"the archive is larger than {max_bytes // 1_000_000} MB")
                    chunks.append(chunk)
                return b"".join(chunks)
        except httpx.HTTPError as exc:
            raise ConnectorError("unavailable", f"{self.system} did not answer") from exc
