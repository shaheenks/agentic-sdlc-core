"""Fake Entra issuer: mints RS256 tokens shaped like Entra v2 access tokens (tests only)."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from fastmcp.server.auth.providers.jwt import RSAKeyPair
from sdlc_auth.entra import EntraTokenVerifier, entra_issuer

TENANT = "11111111-2222-3333-4444-555555555555"
API_CLIENT = "66666666-7777-8888-9999-000000000000"
TEST_ENV = {"ENTRA_TENANT_ID": TENANT, "ENTRA_API_CLIENT_ID": API_CLIENT}

# Entra app role values (the `roles` claim). Membership comes only from app roles and users.yaml
# (CH-0011); the G_ names are kept from when these were group object IDs.
G_ENG_ALL = "SDLC.User"
G_PAYMENTS_DEVS = "SDLC.Payments.Member"
G_PAYMENTS_LEADS = "SDLC.Payments.Approver"
G_PLATFORM_DEVS = "SDLC.Platform.Member"
G_PLATFORM_ADMINS = "SDLC.Admin"
G_INFRA_READERS = "SDLC.Infra.Reader"  # fixture-only app role: the platform-infra source's audience


@dataclass
class FakeEntra:
    tenant: str = TENANT
    audience: str = API_CLIENT
    key: RSAKeyPair = field(default_factory=RSAKeyPair.generate)

    def token(
        self,
        *,
        oid: str | None = None,
        roles: list[str] | None = None,
        upn: str = "user@example.com",
        expires_in: int = 3600,
        audience: str | None = None,
        issuer: str | None = None,
        key: RSAKeyPair | None = None,
        **claims: Any,
    ) -> str:
        """Mint a token. `roles` = app roles (default: SDLC.User). Extra kwargs override claims
        (e.g. `groups=[...]`, which the server ignores); `omit=[...]` drops default claims."""
        omit = set(claims.pop("omit", []))
        subject = oid or str(uuid.uuid4())
        body: dict[str, Any] = {
            "tid": self.tenant,
            "oid": subject,
            "scp": "access_as_user",
            "ver": "2.0",
            "preferred_username": upn,
            "name": upn.split("@")[0],
            "roles": roles if roles is not None else [G_ENG_ALL],
        }
        body.update(claims)
        for name in omit:
            body.pop(name, None)
        return (key or self.key).create_token(
            subject=subject,
            issuer=issuer or entra_issuer(self.tenant),
            audience=audience or self.audience,
            expires_in_seconds=expires_in,
            additional_claims=body,
        )

    def verifier(self, **kwargs: Any) -> EntraTokenVerifier:
        return EntraTokenVerifier(
            tenant_id=self.tenant,
            audience=[self.audience, f"api://{self.audience}"],
            required_scopes=["access_as_user"],
            public_key=self.key.public_key,
            **kwargs,
        )
