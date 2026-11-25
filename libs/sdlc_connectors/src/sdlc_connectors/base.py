"""What every adapter shares: one HTTP client per call, errors mapped to a small set of codes, and nothing of the
credential, the request or the response body in an error message."""

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
            raise ConnectorError(code, f"{self.system} answered {response.status_code} ({code})")
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text
