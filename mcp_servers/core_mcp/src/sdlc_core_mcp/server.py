"""Core MCP server (core_mcp): the Entra stack's server.

The server itself (tools, policy middleware, audit, artifacts, connections) is `sdlc_mcp`, shared
with other server components (CH-0020). This component supplies only the Entra parts: the token
verifier with OAuth protected-resource metadata, and the Entra identity adapter.
"""

from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider, RemoteAuthProvider
from sdlc_auth.entra import EntraTokenVerifier
from sdlc_config import ConfigStore, Snapshot
from sdlc_mcp import server as shared
from sdlc_mcp.artifact_tools import Artifacts
from sdlc_mcp.connected_tools import Connected
from sdlc_mcp.knowledge_tools import Knowledge

from sdlc_core_mcp.entra import ENTRA


def build_server(
    store: ConfigStore,
    auth: AuthProvider,
    knowledge: Knowledge | None = None,
    connected: Connected | None = None,
    artifacts: Artifacts | None = None,
) -> FastMCP:
    return shared.build_server(store, auth, knowledge, connected, artifacts, identity=ENTRA)


def build_http_app(server: FastMCP, store: ConfigStore):
    return shared.build_http_app(server, store, ENTRA)


def build_auth(
    snapshot: Snapshot, public_url: str, store: ConfigStore | None = None
) -> RemoteAuthProvider:
    """Entra token verification + OAuth protected-resource metadata (RFC 9728).

    The 401 WWW-Authenticate header points MCP clients (e.g. Antigravity) at
    /.well-known/oauth-protected-resource, which names Entra as the authorization server.
    Identity settings are read once at startup; changing them needs a restart. The block list
    (E3) is read from the store's current snapshot on every request, so it applies on reload.
    """
    platform = snapshot.platform
    verifier = EntraTokenVerifier(
        tenant_id=platform.tenant_id,
        audience=list(platform.audience),
        required_scopes=list(platform.required_scopes),
        issuer=platform.issuer,
        jwks_uri=platform.jwks_uri,
        blocked_reason=(lambda oid: store.current().blocked.get(oid)) if store else None,
    )
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[platform.issuer],
        base_url=public_url,
        resource_name="sdlc-mcp",
    )


def main() -> None:
    shared.serve(ENTRA, build_auth)


if __name__ == "__main__":
    main()
