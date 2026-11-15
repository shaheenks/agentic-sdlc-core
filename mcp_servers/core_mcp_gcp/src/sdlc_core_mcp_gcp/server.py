"""Core MCP server of the GCP stack (core_mcp_gcp, CH-0022).

The server itself (tools, policy middleware, audit, artifacts, connections) is `sdlc_mcp`, shared
with core_mcp (CH-0020). This component supplies only the Google parts (CH-0021):
- the token verifier: a Google ID token for one of our OAuth clients (`SDLC_OAUTH_CLIENT_IDS`,
  not committed), from a domain in `platform.yaml` `identity.google.allowed_domains`;
- the identity adapter: the user is `sub`, membership is the configured Google groups the user is
  in (Cloud Identity Groups API, as this service's own account: Groups Reader), users.yaml by
  verified email.
Missing settings stop startup (fail closed). Identity settings are read once at startup; the
block list (by `sub`) is read from the current snapshot on every request.
"""

import os
import re
from collections.abc import Mapping

from fastmcp.server.auth import RemoteAuthProvider
from sdlc_auth.google import GOOGLE_ISSUER, GoogleAdapter, GoogleTokenVerifier
from sdlc_auth.groups import CloudIdentityGroups, GroupDirectory, adc_token_provider
from sdlc_config import ConfigStore, Snapshot
from sdlc_mcp import server as shared

NAME = "sdlc-core-mcp-gcp"
_CLIENT_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)  # e.g. <n>-<hash>.apps.googleusercontent.com


def oauth_client_ids(environ: Mapping[str, str] = os.environ) -> list[str]:
    """Our OAuth client IDs (the ID token audience), from SDLC_OAUTH_CLIENT_IDS."""
    clients = [c.strip() for c in environ.get("SDLC_OAUTH_CLIENT_IDS", "").split(",")]
    clients = [c for c in clients if c]
    if not clients:
        raise SystemExit("SDLC_OAUTH_CLIENT_IDS must be set (fail closed)")
    malformed = [c for c in clients if not _CLIENT_ID.match(c)]
    if malformed:  # e.g. a .env comment taken as a value: every token would fail, so stop here
        raise SystemExit(
            f"SDLC_OAUTH_CLIENT_IDS has {len(malformed)} malformed entries (fail closed)"
        )
    return clients


def _google(snapshot: Snapshot):
    google = snapshot.platform.google
    if google is None:
        raise SystemExit("platform.yaml identity.google is required on the GCP stack (fail closed)")
    return google


def build_identity(
    snapshot: Snapshot,
    directory: GroupDirectory | None = None,
    environ: Mapping[str, str] = os.environ,
) -> GoogleAdapter:
    """The Google adapter with the configured group lookup (`direct` on Cloud Identity Free)."""
    google = _google(snapshot)
    if directory is None:
        directory = CloudIdentityGroups(
            mode=google.group_lookup,
            cache_seconds=google.group_cache_seconds,
            token=adc_token_provider(),
            # local runs with your own ADC bill the API to this project (compose sets it)
            quota_project=environ.get("GOOGLE_CLOUD_QUOTA_PROJECT") or None,
        )
    return GoogleAdapter(directory, audience=oauth_client_ids(environ))


def build_auth(
    snapshot: Snapshot,
    public_url: str,
    store: ConfigStore | None = None,
    environ: Mapping[str, str] = os.environ,
) -> RemoteAuthProvider:
    """Google ID token verification + OAuth protected-resource metadata (RFC 9728)."""
    verifier = GoogleTokenVerifier(
        audience=oauth_client_ids(environ),
        allowed_domains=list(_google(snapshot).allowed_domains),
        blocked_reason=(lambda sub: store.current().blocked.get(sub.lower())) if store else None,
    )
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[GOOGLE_ISSUER],
        base_url=public_url,
        resource_name=NAME,
    )


def main() -> None:
    # This server is the GCP stack: the config loader then needs no Entra settings (CH-0022).
    os.environ.setdefault("SDLC_IDENTITY_PROVIDER", "google")
    shared.serve(build_identity, build_auth, name=NAME)


if __name__ == "__main__":
    main()
