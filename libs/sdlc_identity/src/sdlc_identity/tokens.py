"""Proof that a token is a valid Google token, with a per-instance cache."""

import asyncio
import hashlib
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import jwt

GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
GOOGLE_CERTS = "https://www.googleapis.com/oauth2/v3/certs"
TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
CACHE_LIMIT = 10_000


class Rejected(Exception):
    """The caller is refused; `reason` goes to the audit record."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


Claims = dict[str, Any]
"""Normalised claims: sub, email, email_verified, hd, client_id, scopes (None for ID tokens), exp, kind."""


def _looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2 and token.startswith("eyJ")


class GoogleTokens:
    def __init__(
        self,
        *,
        cache_seconds: int = 300,
        clock: Callable[[], float] = time.time,
        http: httpx.AsyncClient | None = None,
        verify_id_token: Callable[[str], Claims] | None = None,
        introspect: Callable[[str], Awaitable[dict]] | None = None,
    ) -> None:
        self.cache_seconds = cache_seconds
        self._clock = clock
        self._http = http
        self._jwks: jwt.PyJWKClient | None = None
        self._verify_id_token = verify_id_token or self._verify_with_google_keys
        self._introspect = introspect or self._tokeninfo
        self._cache: dict[str, tuple[float, Claims]] = {}

    async def claims(self, token: str) -> Claims:
        if not token:
            raise Rejected("no_token")
        key = hashlib.sha256(token.encode()).hexdigest()
        now = self._clock()
        hit = self._cache.get(key)
        if hit is not None and hit[0] > now:
            return hit[1]
        if _looks_like_jwt(token):
            claims = await asyncio.to_thread(self._id_token_claims, token)
        else:
            claims = self._access_token_claims(await self._introspect(token))
        if claims["exp"] <= now:
            raise Rejected("expired")
        if len(self._cache) >= CACHE_LIMIT:
            self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
        self._cache[key] = (min(now + self.cache_seconds, claims["exp"]), claims)
        return claims

    # ID tokens --------------------------------------------------------------------------------------------

    def _id_token_claims(self, token: str) -> Claims:
        try:
            raw = self._verify_id_token(token)
        except jwt.ExpiredSignatureError as exc:
            raise Rejected("expired") from exc
        except (jwt.PyJWTError, ValueError) as exc:
            raise Rejected("invalid_token") from exc
        return {
            "kind": "id",
            "sub": str(raw.get("sub", "")),
            "email": str(raw.get("email", "")).lower(),
            "email_verified": raw.get("email_verified") is True,
            "hd": str(raw.get("hd") or "").lower() or None,
            "client_id": str(raw.get("aud", "")),
            "scopes": None,
            "exp": int(raw.get("exp", 0)),
        }

    def _verify_with_google_keys(self, token: str) -> Claims:
        if self._jwks is None:
            self._jwks = jwt.PyJWKClient(GOOGLE_CERTS, cache_keys=True, lifespan=3600)
        key = self._jwks.get_signing_key_from_jwt(token)
        # The audience (our OAuth clients) is checked by `check` against the active configuration.
        return jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=GOOGLE_ISSUERS,
            options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
        )

    # Access tokens ----------------------------------------------------------------------------------------

    async def _tokeninfo(self, token: str) -> dict:
        client = self._http or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.post(TOKENINFO, data={"access_token": token})
        except httpx.HTTPError as exc:
            raise Rejected("introspection_failed") from exc
        finally:
            if self._http is None:
                await client.aclose()
        if response.status_code != 200:
            raise Rejected("invalid_token")
        return response.json()

    @staticmethod
    def _access_token_claims(info: dict) -> Claims:
        try:
            exp = int(info["exp"])
        except (KeyError, TypeError, ValueError) as exc:
            raise Rejected("invalid_token") from exc
        email_verified = info.get("email_verified")
        return {
            "kind": "access",
            "sub": str(info.get("sub", "")),
            "email": str(info.get("email", "")).lower(),
            "email_verified": email_verified is True or str(email_verified).lower() == "true",
            "hd": None,
            "client_id": str(info.get("aud") or info.get("azp") or ""),
            "scopes": tuple(str(info.get("scope", "")).split()),
            "exp": exp,
        }
