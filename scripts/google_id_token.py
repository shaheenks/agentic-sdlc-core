"""Sign in with Google in the browser and get your Google ID token (GCP stack, CH-0022).

For manual checks only (`agent_runtime_query.py --idp google`, `mcp_whoami.py --idp google`).
It runs the OAuth installed-app flow for a *Desktop app* OAuth client of the GCP stack: a browser
opens on Google's sign-in page, Google redirects to a one-off listener on 127.0.0.1, and the code is
exchanged (with PKCE) for tokens. The ID token's audience is the Desktop client, so its id must be
in SDLC_OAUTH_CLIENT_IDS beside the web client's. Settings (from .env, never committed):
  SDLC_GOOGLE_DESKTOP_CLIENT_ID, SDLC_GOOGLE_DESKTOP_CLIENT_SECRET
(a Desktop client's secret is not confidential, Google says, but it stays out of git anyway).

    uv run --env-file .env python scripts/google_id_token.py --print   # print the token (to pipe)

Nothing is stored; the token is printed only with --print.
"""

import argparse
import base64
import hashlib
import http.server
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 (an endpoint, not a secret)


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def authorization_url(client_id: str, redirect: str, state: str, challenge: str, hd: str) -> str:
    query = {
        "client_id": client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    if hd:
        query["hd"] = hd  # a hint for the account picker; the server checks `hd` itself
    return f"{AUTH_URL}?{urllib.parse.urlencode(query)}"


def _wait_for_code(state: str) -> tuple[http.server.HTTPServer, dict]:
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if params.get("state") == state and "code" in params:
                result["code"] = params["code"]
                body = b"Signed in. You can close this tab."
            else:
                result["error"] = params.get("error", "state mismatch")
                body = b"Sign-in failed. You can close this tab."
            self.send_response(200)
            self.send_header("content-type", "text/plain")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # no request logging (the URL carries the code)
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    return server, result


def id_token(hd: str = "", environ=os.environ) -> str:
    """Your Google ID token for the Desktop client (opens the browser)."""
    import httpx

    client_id = environ.get("SDLC_GOOGLE_DESKTOP_CLIENT_ID", "")
    client_secret = environ.get("SDLC_GOOGLE_DESKTOP_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        sys.exit("set SDLC_GOOGLE_DESKTOP_CLIENT_ID and SDLC_GOOGLE_DESKTOP_CLIENT_SECRET in .env")
    state = secrets.token_urlsafe(24)
    verifier, challenge = _pkce()
    server, result = _wait_for_code(state)
    redirect = f"http://127.0.0.1:{server.server_address[1]}"
    url = authorization_url(client_id, redirect, state, challenge, hd)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    print(f"opening the browser to sign in (or open this URL):\n{url}", file=sys.stderr)
    webbrowser.open(url)
    thread.join(timeout=300)
    server.server_close()
    if "code" not in result:
        sys.exit(f"sign-in failed: {result.get('error', 'timed out')}")
    response = httpx.post(
        TOKEN_URL,
        data={
            "code": result["code"],
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
        timeout=30,
    )
    if response.status_code != 200 or "id_token" not in response.json():
        sys.exit(f"token exchange failed ({response.status_code})")  # never the body
    return response.json()["id_token"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--hd", default="", help="Cloud Identity domain hint for the account picker"
    )
    parser.add_argument("--print", action="store_true", help="print the ID token")
    args = parser.parse_args()
    token = id_token(args.hd)
    print(token if args.print else "signed in (pass --print to print the token)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
