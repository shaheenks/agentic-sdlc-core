"""HTTP for remote loaders (version-01 M0): host allowlist, timeouts, retries, credentials.

- Every request URL, and every redirect target, must be https on a host in platform.yaml
  knowledge.allowed_hosts (SSRF guard); redirects are followed manually, at most MAX_REDIRECTS.
- 429 and 5xx (and connection errors) are retried with exponential backoff, honouring
  `Retry-After` (seconds or an HTTP date), up to `max_attempts`; the wait is capped.
- Credentials are a callable returning headers, called per request, so a secret is revealed only
  at send time, and only to the request's own host (not to a cross-host redirect target).
  After a 401 the client calls `on_unauthorized` (drop the cached secret) and retries once with
  fresh headers.
- Nothing about requests is logged here; errors carry method, host and status, never headers.
"""

import email.utils
import random
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from urllib.parse import urljoin

import httpx
from sdlc_config.hosts import url_allowed, url_host

from sdlc_loaders.base import LoaderError

MAX_REDIRECTS = 3
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class HttpError(LoaderError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class HostNotAllowed(HttpError):
    pass


def _retry_after(response: httpx.Response, now: float) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    if value.strip().isdigit():
        return float(value.strip())
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - now)


class HttpClient:
    def __init__(
        self,
        allowed_hosts: Iterable[str],
        *,
        auth_headers: Callable[[], Mapping[str, str]] | None = None,
        on_unauthorized: Callable[[], None] | None = None,
        timeout: float = 30.0,
        max_attempts: int = 5,
        backoff: float = 1.0,
        max_wait: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        user_agent: str = "agentic-sdlc-ingest",
    ) -> None:
        self.allowed_hosts = tuple(allowed_hosts)
        self._auth_headers = auth_headers
        self._on_unauthorized = on_unauthorized
        self._max_attempts = max(1, max_attempts)
        self._backoff, self._max_wait = backoff, max_wait
        self._sleep = sleep
        self._client = httpx.Client(
            transport=transport,
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _check(self, url: str) -> None:
        if not url_allowed(url, self.allowed_hosts):
            host = url_host(url) or "(not an https URL)"
            raise HostNotAllowed(f"host {host} is not in platform.yaml knowledge.allowed_hosts")

    def _wait(self, attempt: int, response: httpx.Response | None) -> float:
        hinted = _retry_after(response, time.time()) if response is not None else None
        if hinted is None:
            hinted = self._backoff * (2 ** (attempt - 1)) * (1 + random.random() / 4)  # noqa: S311
        return min(hinted, self._max_wait)

    def request(
        self, method: str, url: str, *, params: Mapping[str, Any] | None = None, **kwargs
    ) -> httpx.Response:
        extra_headers = dict(kwargs.pop("headers", None) or {})
        refreshed = False
        attempt = 0
        while True:
            attempt += 1
            response = self._send(method, url, params, extra_headers, kwargs)
            status = response.status_code if response is not None else None
            if status == 401 and self._on_unauthorized is not None and not refreshed:
                refreshed = True  # the secret may have been rotated: re-read it once
                self._on_unauthorized()
                attempt -= 1
                continue
            if status is not None and status not in RETRY_STATUSES:
                if status >= 400:
                    raise HttpError(f"{method} {url_host(url)} returned {status}", status=status)
                return response
            if attempt >= self._max_attempts:
                what = f"returned {status}" if status else "failed (connection error)"
                raise HttpError(
                    f"{method} {url_host(url)} {what} after {attempt} attempts", status=status
                )
            self._sleep(self._wait(attempt, response))

    def _send(self, method, url, params, extra_headers, kwargs) -> httpx.Response | None:
        """One request, following allowed redirects. None on a connection error (retried)."""
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            self._check(current)
            headers = dict(extra_headers)
            # credentials go to the host the request was made for, never to a redirect target
            # on another host (e.g. a pre-signed download URL on a media/CDN host)
            if self._auth_headers is not None and url_host(current) == url_host(url):
                headers.update(self._auth_headers())
            try:
                response = self._client.request(
                    method, current, params=params, headers=headers, **kwargs
                )
            except httpx.TransportError:
                return None
            if response.is_redirect:
                location = response.headers.get("Location", "")
                current, params = urljoin(current, location), None
                continue
            return response
        raise HttpError(f"{method} {url_host(url)}: too many redirects")

    def get_json(self, url: str, *, params: Mapping[str, Any] | None = None) -> Any:
        response = self.request("GET", url, params=params)
        try:
            return response.json()
        except ValueError as e:
            raise HttpError(f"GET {url_host(url)}: response is not JSON") from e
