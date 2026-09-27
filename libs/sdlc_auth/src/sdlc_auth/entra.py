"""Entra ID v2 access-token verification for MCP servers (fastmcp TokenVerifier).

fastmcp's JWTVerifier checks signature (JWKS), exp, iss, aud and required scopes, and makes
the server answer 401 + WWW-Authenticate. On top of that we require:
  - tid == our tenant (defense in depth; the issuer already embeds it)
  - an oid claim (a real directory object)
  - a delegated user token: app-only tokens (idtyp=app, no scp) are rejected
"""

import logging
from collections.abc import Callable

from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.providers.jwt import JWTVerifier

log = logging.getLogger("sdlc.auth")


# Commercial cloud. MCP servers take the host from platform.yaml identity/authority_host; the
# agent web app (which never reads config) from ENTRA_AUTHORITY_HOST. Sovereign clouds: E7.
DEFAULT_AUTHORITY_HOST = "https://login.microsoftonline.com"


def entra_issuer(tenant_id: str, authority_host: str = DEFAULT_AUTHORITY_HOST) -> str:
    return f"{authority_host.rstrip('/')}/{tenant_id}/v2.0"


def entra_jwks_uri(tenant_id: str, authority_host: str = DEFAULT_AUTHORITY_HOST) -> str:
    return f"{authority_host.rstrip('/')}/{tenant_id}/discovery/v2.0/keys"


class EntraTokenVerifier(JWTVerifier):
    def __init__(
        self,
        *,
        tenant_id: str,
        audience: list[str],
        required_scopes: list[str],
        issuer: str | None = None,
        jwks_uri: str | None = None,
        public_key: str | bytes | None = None,  # tests only; production uses JWKS
        base_url: str | None = None,
        authority_host: str = DEFAULT_AUTHORITY_HOST,  # used when issuer/jwks_uri are not given
        blocked_reason: Callable[[str], str | None] | None = None,  # E3: oid -> reason if blocked
    ):
        self.tenant_id = tenant_id
        self.blocked_reason = blocked_reason
        jwks_uri = jwks_uri or entra_jwks_uri(tenant_id, authority_host)
        super().__init__(
            public_key=public_key,
            jwks_uri=None if public_key else jwks_uri,
            issuer=issuer or entra_issuer(tenant_id, authority_host),
            audience=audience,
            algorithm="RS256",
            required_scopes=required_scopes,
            base_url=base_url,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        access = await super().load_access_token(token)
        if access is None:
            return None
        claims = access.claims
        if claims.get("tid") != self.tenant_id:
            log.info("token rejected: tenant mismatch (tid=%r)", claims.get("tid"))
            return None
        if not claims.get("oid"):
            log.info("token rejected: no oid claim")
            return None
        if claims.get("idtyp") == "app" or not claims.get("scp"):
            log.info("token rejected: not a delegated user token")
            return None
        if self.blocked_reason is not None:
            reason = self.blocked_reason(str(claims["oid"]).lower())
            if reason is not None:
                log.warning("token rejected: user oid=%s is blocked (%s)", claims["oid"], reason)
                return None
        return access
