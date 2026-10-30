"""Host allowlist (SSRF guard, version-01 M0): the hosts ingest may contact for remote sources.

platform.yaml knowledge.allowed_hosts lists exact host names (`github.com`) or one leading wildcard
label (`*.atlassian.net` matches `acme.atlassian.net`, not `atlassian.net` itself). Matching is
case-insensitive; ports and user info are not part of a host and never match.
"""

from collections.abc import Iterable
from urllib.parse import urlsplit


def host_allowed(host: str, allowed: Iterable[str]) -> bool:
    host = (host or "").lower().rstrip(".")
    if not host:
        return False
    for pattern in allowed:
        pattern = pattern.lower()
        if pattern.startswith("*."):
            suffix = pattern[1:]  # ".atlassian.net"
            label = host[: -len(suffix)] if host.endswith(suffix) else ""
            if label and "." not in label:
                return True
        elif host == pattern:
            return True
    return False


def url_host(url: str) -> str | None:
    """Host of an https URL, or None for anything else (http, ssh, credentials in the URL)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return None
    return parts.hostname


def url_allowed(url: str, allowed: Iterable[str]) -> bool:
    host = url_host(url)
    return host is not None and host_allowed(host, allowed)
