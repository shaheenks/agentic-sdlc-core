"""Fake Google issuer: mints RS256 tokens shaped like Google ID tokens (tests only, CH-0021).

Client IDs and the domain are placeholders, never a real OAuth client or Cloud Identity domain.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from fastmcp.server.auth.providers.jwt import RSAKeyPair
from sdlc_auth.google import GOOGLE_ISSUER, GoogleTokenVerifier

from tests.support.config import GOOGLE_DOMAIN

CLIENT_ID = "000000000000-fixture.apps.googleusercontent.com"
OTHER_CLIENT_ID = "999999999999-someone-else.apps.googleusercontent.com"


@dataclass
class FakeGoogle:
    audience: str = CLIENT_ID
    domain: str = GOOGLE_DOMAIN
    key: RSAKeyPair = field(default_factory=RSAKeyPair.generate)

    def token(
        self,
        *,
        sub: str | None = None,
        email: str = f"user@{GOOGLE_DOMAIN}",
        expires_in: int = 3600,
        audience: str | None = None,
        issuer: str = GOOGLE_ISSUER,
        key: RSAKeyPair | None = None,
        **claims: Any,
    ) -> str:
        """Mint an ID token. Extra kwargs override claims; `omit=[...]` drops default claims."""
        omit = set(claims.pop("omit", []))
        subject = sub or str(uuid.uuid4().int)[:21]  # Google subs are ~21 digits
        body: dict[str, Any] = {
            "email": email,
            "email_verified": True,
            "hd": self.domain,
            "name": email.split("@")[0],
            "azp": self.audience,
        }
        body.update(claims)
        for name in omit:
            body.pop(name, None)
        return (key or self.key).create_token(
            subject=subject,
            issuer=issuer,
            audience=audience or self.audience,
            expires_in_seconds=expires_in,
            additional_claims=body,
        )

    def verifier(self, **kwargs: Any) -> GoogleTokenVerifier:
        return GoogleTokenVerifier(
            audience=[self.audience],
            allowed_domains=[self.domain],
            public_key=self.key.public_key,
            **kwargs,
        )
