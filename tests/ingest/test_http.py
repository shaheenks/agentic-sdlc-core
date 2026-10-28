"""version-01 M0: HTTP for remote loaders (allowlist, retries, credentials), recorded responses."""

import httpx
import pytest
from sdlc_loaders.http import HostNotAllowed, HttpClient, HttpError

TOKEN = "pat-value-never-in-errors"  # noqa: S105 (test value)
ALLOWED = ["api.example.com", "*.atlassian.net"]


def client(handler, **kw):
    sleeps = []
    c = HttpClient(
        ALLOWED,
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        backoff=1.0,
        **kw,
    )
    return c, sleeps


def test_get_json_and_auth_headers_per_request():
    calls = []

    def handler(request):
        calls.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"ok": True})

    tokens = iter(["Bearer one", "Bearer two"])
    c, _ = client(handler, auth_headers=lambda: {"Authorization": next(tokens)})
    assert c.get_json("https://api.example.com/x") == {"ok": True}
    assert c.get_json("https://acme.atlassian.net/rest/api/3/search") == {"ok": True}
    assert calls == ["Bearer one", "Bearer two"]


@pytest.mark.parametrize(
    "url",
    [
        "https://internal.corp/metadata",
        "http://api.example.com/x",  # https only
        "https://169.254.169.254/computeMetadata/v1/",
        "https://atlassian.net/x",
    ],
)
def test_hosts_outside_the_allowlist_are_never_contacted(url):
    contacted = []
    c, _ = client(lambda r: contacted.append(r) or httpx.Response(200))
    with pytest.raises(HostNotAllowed):
        c.request("GET", url)
    assert contacted == []


def test_redirects_are_checked_against_the_allowlist():
    def handler(request):
        if request.url.host == "api.example.com":
            return httpx.Response(302, headers={"Location": "https://internal.corp/secret"})
        raise AssertionError("redirect target must not be contacted")

    c, _ = client(handler)
    with pytest.raises(HostNotAllowed):
        c.request("GET", "https://api.example.com/x")


def test_allowed_redirects_are_followed():
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(301, headers={"Location": "/new"})
        return httpx.Response(200, json={"path": request.url.path})

    c, _ = client(handler)
    assert c.get_json("https://api.example.com/old") == {"path": "/new"}


def test_429_honours_retry_after_then_succeeds():
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(503),
            httpx.Response(200, json=[1]),
        ]
    )
    c, sleeps = client(lambda r: next(responses))
    assert c.get_json("https://api.example.com/x") == [1]
    assert sleeps[0] == 7.0  # Retry-After
    assert 2.0 <= sleeps[1] <= 2.5  # exponential backoff (attempt 2) with jitter


def test_retry_after_is_capped():
    responses = iter([httpx.Response(429, headers={"Retry-After": "3600"}), httpx.Response(200)])
    c, sleeps = client(lambda r: next(responses), max_wait=60)
    c.request("GET", "https://api.example.com/x")
    assert sleeps == [60]


def test_retries_give_up_with_a_clear_error():
    c, sleeps = client(lambda r: httpx.Response(502), max_attempts=3)
    with pytest.raises(HttpError, match="returned 502 after 3 attempts") as exc:
        c.request("GET", "https://api.example.com/x")
    assert exc.value.status == 502 and len(sleeps) == 2


def test_connection_errors_are_retried():
    state = {"n": 0}

    def handler(request):
        state["n"] += 1
        if state["n"] == 1:
            raise httpx.ConnectError("reset")
        return httpx.Response(200, json={})

    c, sleeps = client(handler)
    assert c.get_json("https://api.example.com/x") == {} and len(sleeps) == 1


def test_401_rereads_the_secret_once():
    seen, invalidated = [], []
    tokens = iter(["Bearer old", "Bearer new"])

    def handler(request):
        seen.append(request.headers["Authorization"])
        return httpx.Response(200 if request.headers["Authorization"] == "Bearer new" else 401)

    c, _ = client(
        handler,
        auth_headers=lambda: {"Authorization": next(tokens)},
        on_unauthorized=lambda: invalidated.append(True),
    )
    assert c.request("GET", "https://api.example.com/x").status_code == 200
    assert seen == ["Bearer old", "Bearer new"] and invalidated == [True]


def test_persistent_401_fails_without_leaking_the_token():
    c, _ = client(
        lambda r: httpx.Response(401, text=f"bad token {TOKEN}"),
        auth_headers=lambda: {"Authorization": f"Bearer {TOKEN}"},
        on_unauthorized=lambda: None,
    )
    with pytest.raises(HttpError) as exc:
        c.request("GET", "https://api.example.com/x")
    assert exc.value.status == 401 and TOKEN not in str(exc.value)


def test_client_errors_are_not_retried():
    c, sleeps = client(lambda r: httpx.Response(404))
    with pytest.raises(HttpError, match="returned 404"):
        c.request("GET", "https://api.example.com/x")
    assert sleeps == []
