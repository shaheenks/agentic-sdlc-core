"""Shared by the Confluence (M3) and Jira (M4) loaders: authentication and the HTTP client.

The source's secret (`spec.credentials`) holds either
  `<email>:<api token>`   Atlassian Cloud API token  -> HTTP Basic
  `<token>`               Data Center personal access token (or a Cloud bearer token) -> Bearer
so one secret per source covers both editions without extra config. The value is read per request
through sdlc_secrets (cached briefly) and dropped from the cache after a 401.
"""

import base64
from collections.abc import Callable

from sdlc_loaders.base import LoaderContext, LoaderError
from sdlc_loaders.http import HttpClient


def auth_header_value(secret: str) -> str:
    if ":" in secret:
        return "Basic " + base64.b64encode(secret.encode()).decode()
    return f"Bearer {secret}"


def atlassian_client(source, ctx: LoaderContext) -> Callable[[], HttpClient]:
    """A factory for an HttpClient that authenticates as the source's service account and may only
    reach platform.yaml knowledge.allowed_hosts (the source host is checked at config load)."""
    if not source.credentials:
        raise LoaderError(f"{source.type} sources need spec.credentials")
    ref = source.credentials

    def headers() -> dict[str, str]:
        if ctx.secrets is None:
            raise LoaderError("no secret resolver given")
        try:
            value = ctx.secrets.resolve(ref).reveal()
        except Exception as e:  # SecretError carries the name, never the value
            raise LoaderError(f"credentials {ref[0]}:{ref[1]}: {e}") from None
        return {"Authorization": auth_header_value(value)}

    def invalidate() -> None:
        if ctx.secrets is not None:
            ctx.secrets.invalidate(ref)

    return lambda: HttpClient(ctx.allowed_hosts, auth_headers=headers, on_unauthorized=invalidate)
