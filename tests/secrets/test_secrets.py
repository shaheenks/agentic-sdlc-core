"""version-01 M0: secret references resolved at runtime (libs/sdlc_secrets)."""

import base64
import json
import pickle

import httpx
import pytest
from sdlc_secrets import (
    EnvSecretStore,
    GcpSecretStore,
    SecretAccessDenied,
    SecretError,
    SecretNotFound,
    SecretRef,
    SecretResolver,
    SecretValue,
    resolver_from_env,
)

TOKEN = "s3cr3t-value-never-logged"  # noqa: S105 (test value)


# --- references and values ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"env": "JIRA_TOKEN"}, SecretRef("env", "JIRA_TOKEN")),
        ({"secret": "jira-payments-token"}, SecretRef("secret", "jira-payments-token")),
        (("secret", "a1"), SecretRef("secret", "a1")),
    ],
)
def test_refs_parse(value, expected):
    assert SecretRef.parse(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        {"env": "lower_case"},
        {"secret": "Upper"},
        {"secret": "has_underscore"},
        {"vault": "x"},
        {"env": "A", "secret": "a"},
        {},
    ],
)
def test_bad_refs_are_refused(value):
    with pytest.raises(ValueError):
        SecretRef.parse(value)


def test_ref_prints_only_its_name():
    assert str(SecretRef("secret", "jira-token")) == "secret:jira-token"


def test_secret_value_is_masked_and_not_picklable():
    value = SecretValue(TOKEN)
    assert value.reveal() == TOKEN
    assert TOKEN not in repr(value) and TOKEN not in str(value) and TOKEN not in f"{value}"
    assert TOKEN not in repr({"token": value})
    with pytest.raises(TypeError):
        pickle.dumps(value)
    with pytest.raises(ValueError):
        SecretValue("")


# --- env backend + resolver -----------------------------------------------------------------------


def test_env_store_maps_secret_names_to_env_vars():
    store = EnvSecretStore({"SDLC_SECRET_JIRA_PAYMENTS_TOKEN": TOKEN})
    assert store.get("jira-payments-token") == TOKEN
    with pytest.raises(SecretNotFound) as exc:
        store.get("missing-token")
    assert "SDLC_SECRET_MISSING_TOKEN" in str(exc.value)


def test_resolver_reads_env_refs_and_store_refs():
    environ = {"JIRA_TOKEN": "a", "SDLC_SECRET_JIRA_TOKEN": "b"}
    resolver = SecretResolver(EnvSecretStore(environ), environ)
    assert resolver.resolve({"env": "JIRA_TOKEN"}).reveal() == "a"
    assert resolver.resolve({"secret": "jira-token"}).reveal() == "b"
    with pytest.raises(SecretNotFound):
        resolver.resolve({"env": "NOT_SET"})


class CountingStore:
    name = "counting"

    def __init__(self):
        self.calls, self.value = 0, "v1"

    def get(self, name):
        self.calls += 1
        return self.value


def test_resolver_caches_until_ttl_and_invalidate():
    store, now = CountingStore(), [0.0]
    resolver = SecretResolver(store, {}, ttl=300, clock=lambda: now[0])
    ref = {"secret": "jira-token"}
    assert resolver.resolve(ref).reveal() == "v1"
    store.value = "v2"  # rotated in the store
    now[0] = 299
    assert resolver.resolve(ref).reveal() == "v1" and store.calls == 1  # cached
    now[0] = 301
    assert resolver.resolve(ref).reveal() == "v2" and store.calls == 2  # expired: re-read
    store.value = "v3"
    resolver.invalidate(ref)  # e.g. after a 401 from the downstream
    assert resolver.resolve(ref).reveal() == "v3" and store.calls == 3


def test_resolver_from_env_selects_backend():
    assert resolver_from_env({}).store.name == "env"
    gcp = resolver_from_env(
        {
            "SDLC_SECRETS_BACKEND": "gcp",
            "GOOGLE_CLOUD_PROJECT": "proj",
            "SDLC_SECRETS_LOCATION": "asia-south1",
        }
    ).store
    assert (gcp.name, gcp.project, gcp.location) == ("gcp", "proj", "asia-south1")
    with pytest.raises(SecretError):
        resolver_from_env({"SDLC_SECRETS_BACKEND": "gcp"})  # no project
    with pytest.raises(SecretError):
        resolver_from_env({"SDLC_SECRETS_BACKEND": "vault"})


# --- Secret Manager backend (REST, recorded responses) ----------------------------------------


def gcp_store(handler, location=None, quota=None):
    return GcpSecretStore(
        "proj",
        location,
        token_provider=lambda: "ya29.test",
        transport=httpx.MockTransport(handler),
        quota_project=quota,
    )


def payload(value: str) -> httpx.Response:
    data = base64.b64encode(value.encode()).decode()
    return httpx.Response(200, json={"name": "x", "payload": {"data": data}})


def test_gcp_store_reads_latest_global_version():
    seen = {}

    def handler(request):
        seen["url"], seen["headers"] = str(request.url), request.headers
        return payload(TOKEN)

    assert gcp_store(handler, quota="quota-proj").get("jira-token") == TOKEN
    assert seen["url"] == (
        "https://secretmanager.googleapis.com/v1/projects/proj/secrets/jira-token/versions/"
        "latest:access"
    )
    assert seen["headers"]["Authorization"] == "Bearer ya29.test"
    assert seen["headers"]["x-goog-user-project"] == "quota-proj"


def test_gcp_store_uses_the_regional_endpoint_for_regional_secrets():
    urls = []

    def handler(request):
        urls.append(str(request.url))
        return payload("v")

    gcp_store(handler, location="asia-south1").get("jira-token")
    assert urls == [
        "https://secretmanager.asia-south1.rep.googleapis.com/v1/projects/proj/locations/"
        "asia-south1/secrets/jira-token/versions/latest:access"
    ]


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (404, SecretNotFound),
        (403, SecretAccessDenied),
        (401, SecretAccessDenied),
        (500, SecretError),
    ],
)
def test_gcp_store_errors_carry_no_response_body(status, error):
    body = {"error": {"message": f"leaky detail {TOKEN}"}}
    store = gcp_store(lambda request: httpx.Response(status, json=body))
    with pytest.raises(error) as exc:
        store.get("jira-token")
    assert TOKEN not in str(exc.value) and "jira-token" in str(exc.value)


def test_gcp_store_rejects_malformed_responses():
    store = gcp_store(lambda request: httpx.Response(200, content=json.dumps({"x": 1})))
    with pytest.raises(SecretError, match="unexpected"):
        store.get("jira-token")


def test_gcp_store_connection_errors_are_secret_errors():
    def handler(request):
        raise httpx.ConnectError("boom")

    with pytest.raises(SecretError, match="unreachable"):
        gcp_store(handler).get("jira-token")
