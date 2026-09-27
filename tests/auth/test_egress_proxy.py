"""E8: token validation works behind an egress proxy (standard HTTP(S)_PROXY / NO_PROXY variables).

The JWKS host below resolves nowhere, so a token can only verify if the signing keys were fetched
through the proxy. Plain HTTP keeps the test free of TLS setup; HTTPS JWKS URIs (Entra) use the
same environment-driven proxy selection via HTTPS_PROXY (CONNECT tunnel).
"""

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from sdlc_auth.entra import EntraTokenVerifier

from tests.support.entra import TENANT, FakeEntra

JWKS_HOST = "login.proxy-test.invalid"
JWKS_URI = f"http://{JWKS_HOST}/{TENANT}/discovery/v2.0/keys"


def _b64(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def jwks_for(entra: FakeEntra) -> dict:
    numbers = load_pem_public_key(entra.key.public_key.encode()).public_numbers()
    return {
        "keys": [
            {"kty": "RSA", "use": "sig", "alg": "RS256", "n": _b64(numbers.n), "e": _b64(numbers.e)}
        ]
    }


@pytest.fixture
def proxy(entra):
    """A forward proxy that answers JWKS requests itself and records the hosts it was asked for."""
    seen: list[str] = []
    body = json.dumps(jwks_for(entra)).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server API
            seen.append(urlsplit(self.path).hostname or "")  # absolute-form: proxied request
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", seen
    server.shutdown()


def verifier(entra: FakeEntra) -> EntraTokenVerifier:
    return EntraTokenVerifier(
        tenant_id=TENANT,
        audience=[entra.audience],
        required_scopes=["access_as_user"],
        jwks_uri=JWKS_URI,
    )


def clear_proxy_env(monkeypatch):
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)


async def test_jwks_is_fetched_through_the_proxy(entra, proxy, monkeypatch):
    url, seen = proxy
    clear_proxy_env(monkeypatch)
    monkeypatch.setenv("HTTP_PROXY", url)
    access = await verifier(entra).load_access_token(entra.token())
    assert access is not None
    assert seen == [JWKS_HOST]


async def test_no_proxy_means_no_keys_and_no_access(entra, monkeypatch):
    clear_proxy_env(monkeypatch)
    assert await verifier(entra).load_access_token(entra.token()) is None  # fail closed


async def test_no_proxy_list_bypasses_the_proxy(entra, proxy, monkeypatch):
    url, seen = proxy
    clear_proxy_env(monkeypatch)
    monkeypatch.setenv("HTTP_PROXY", url)
    monkeypatch.setenv("NO_PROXY", JWKS_HOST)  # sent direct -> unresolvable -> rejected
    assert await verifier(entra).load_access_token(entra.token()) is None
    assert seen == []
