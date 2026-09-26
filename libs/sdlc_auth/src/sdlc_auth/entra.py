"""Entra ID v2 access-token verification for MCP servers (fastmcp TokenVerifier).

fastmcp's JWTVerifier checks signature (JWKS), exp, iss, aud and required scopes, and makes
the server answer 401 + WWW-Authenticate. On top of that we require:
  - tid == our tenant (defense in depth; the issuer already embeds it)
  - an oid claim (a real directory object)
  - a delegated user token: app-only tokens (idtyp=app, no scp) are rejected
"""

import logging

from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.providers.jwt import JWTVerifier

log = logging.getLogger("sdlc.auth")


def entra_issuer(tenant_id: str) -> str:
    return f"https://login.microsoftonline.com/{tenant_id}/v2.0"


def entra_jwks_uri(tenant_id: str) -> str:
    return f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"


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
    ):
        self.tenant_id = tenant_id
        super().__init__(
            public_key=public_key,
            jwks_uri=None if public_key else (jwks_uri or entra_jwks_uri(tenant_id)),
            issuer=issuer or entra_issuer(tenant_id),
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
        return access
