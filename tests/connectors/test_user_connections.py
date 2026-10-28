"""version-01 M6: per-user connections: secret directory stores, provider adapters, service rules.
No network: providers and Secret Manager are fake APIs (httpx.MockTransport)."""

import asyncio
import base64
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from cryptography.fernet import Fernet
from sdlc_config.model import ConnectionDef
from sdlc_connectors import providers
from sdlc_connectors.http import HostNotAllowed
from sdlc_connectors.service import ConnectError, ConnectionService, NotConnected
from sdlc_connectors.user_store import (
    ConnectionEntry,
    FileUserStore,
    GcpUserStore,
    MemoryUserStore,
    UserDirectory,
    UserStoreError,
    store_from_env,
    user_key,
)

OID = "aaaaaaaa-0000-0000-0000-00000000000a"
OTHER = "bbbbbbbb-0000-0000-0000-00000000000b"
PAT = "github_pat_11ABCDEFG_secretvalue"  # noqa: S105 (test value)
TODAY = datetime.now(UTC).date()

GITHUB = ConnectionDef("github", "github", "cloud", "https://api.github.com", max_token_days=90)
JIRA_CLOUD = ConnectionDef("jira-cloud", "jira", "cloud", "https://acme.atlassian.net")
JIRA_DC = ConnectionDef("jira-dc", "jira", "datacenter", "https://jira.example.com")
CONF_CLOUD = ConnectionDef("conf", "confluence", "cloud", "https://acme.atlassian.net")
BB_CLOUD = ConnectionDef("bb", "bitbucket", "cloud", "https://api.bitbucket.org")
BB_DC = ConnectionDef("bb-dc", "bitbucket", "datacenter", "https://bb.example.com")


def entry(token=PAT, **kw):
    now = datetime.now(UTC).isoformat()
    return ConnectionEntry(
        token=token,
        account="octo",
        display="Octo",
        connected_at=now,
        verified_at=now,
        expires_at=(TODAY + timedelta(days=30)).isoformat(),
        **kw,
    )


# --- stores ---------------------------------------------------------------------------------------


def test_directory_roundtrip_and_owner_check():
    directory = UserDirectory(OID, {"github": entry()})
    raw = directory.to_json()
    assert UserDirectory.from_json(raw, OID).connections["github"].token == PAT
    with pytest.raises(UserStoreError, match="owner mismatch"):
        UserDirectory.from_json(raw, OTHER)  # a swapped secret fails closed
    assert PAT not in repr(directory.connections["github"])
    assert "token" not in directory.connections["github"].public()


def test_user_key_hides_the_oid():
    assert len(user_key(OID)) == 32 and OID not in user_key(OID)
    assert user_key(OID) == user_key(OID.upper())


def test_file_store_encrypts(tmp_path):
    key = Fernet.generate_key().decode()
    store = FileUserStore(tmp_path, key)
    store.save(UserDirectory(OID, {"github": entry()}))
    [path] = list(tmp_path.glob("*.bin"))
    assert PAT.encode() not in path.read_bytes() and OID.encode() not in path.read_bytes()
    assert store.load(OID).connections["github"].token == PAT
    assert store.load(OTHER) is None
    with pytest.raises(UserStoreError, match="cannot be decrypted"):
        FileUserStore(tmp_path, Fernet.generate_key().decode()).load(OID)
    store.delete(OID)
    assert store.load(OID) is None
    with pytest.raises(UserStoreError, match="Fernet"):
        FileUserStore(tmp_path, "not-a-key")


class FakeSecretManager:
    def __init__(self):
        self.versions: dict[str, list[bytes]] = {}
        self.destroyed: list[str] = []
        self.calls: list[tuple[str, str]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        assert request.headers["Authorization"] == "Bearer ya29.test"
        prefix = "/v1/projects/proj/secrets"
        if request.method == "GET" and path.endswith("/versions/latest:access"):
            sid = path[len(prefix) + 1 :].split("/")[0]
            if sid not in self.versions:
                return httpx.Response(404)
            data = base64.b64encode(self.versions[sid][-1]).decode()
            return httpx.Response(200, json={"payload": {"data": data}})
        if request.method == "POST" and path.endswith(":addVersion"):
            sid = path[len(prefix) + 1 :].split(":")[0]
            if sid not in self.versions:
                return httpx.Response(404)
            body = json.loads(request.content)
            self.versions[sid].append(base64.b64decode(body["payload"]["data"]))
            return httpx.Response(200, json={})
        if request.method == "POST" and path == prefix:
            self.versions.setdefault(request.url.params["secretId"], [])
            assert json.loads(request.content)["labels"]["kind"] == "user-connections"
            return httpx.Response(200, json={})
        if request.method == "GET" and path.endswith("/versions"):
            sid = path[len(prefix) + 1 :].split("/")[0]
            names = [
                f"projects/proj/secrets/{sid}/versions/{i + 1}"
                for i in range(len(self.versions[sid]))
            ]
            live = [n for n in names if n not in self.destroyed]
            return httpx.Response(200, json={"versions": [{"name": n} for n in live]})
        if request.method == "POST" and path.endswith(":destroy"):
            self.destroyed.append(path[len("/v1/") : -len(":destroy")])
            return httpx.Response(200, json={})
        if request.method == "DELETE":
            self.versions.pop(path[len(prefix) + 1 :], None)
            return httpx.Response(200, json={})
        return httpx.Response(400)


def test_gcp_store_creates_writes_prunes_and_deletes():
    fake = FakeSecretManager()
    store = GcpUserStore(
        "proj",
        "staging",
        token_provider=lambda: "ya29.test",
        transport=httpx.MockTransport(fake.handler),
    )
    sid = store.secret_id(OID)
    assert sid == f"sdlc-staging-user-{user_key(OID)}" and OID not in sid
    assert store.load(OID) is None
    for _ in range(4):
        store.save(UserDirectory(OID, {"github": entry()}))
    assert store.load(OID).connections["github"].token == PAT
    assert fake.destroyed == [
        f"projects/proj/secrets/{sid}/versions/1",
        f"projects/proj/secrets/{sid}/versions/2",
    ]  # newest two kept
    store.delete(OID)
    assert store.load(OID) is None


def test_store_from_env(tmp_path):
    assert store_from_env({}) is None  # connections off
    assert store_from_env({"SDLC_USER_SECRETS_BACKEND": "memory"}).name == "memory"
    key = Fernet.generate_key().decode()
    env = {
        "SDLC_USER_SECRETS_BACKEND": "file",
        "SDLC_USER_SECRETS_KEY": key,
        "SDLC_USER_SECRETS_DIR": str(tmp_path),
    }
    assert store_from_env(env).name == "file"
    with pytest.raises(UserStoreError):
        store_from_env({"SDLC_USER_SECRETS_BACKEND": "file"})
    with pytest.raises(UserStoreError):
        store_from_env({"SDLC_USER_SECRETS_BACKEND": "vault"})


# --- providers ------------------------------------------------------------------------------------


def transport(routes: dict):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        for (method, path), response in routes.items():
            if request.method == method and request.url.path == path:
                return response(request) if callable(response) else response
        return httpx.Response(404)

    return httpx.MockTransport(handler), seen


def test_auth_headers():
    assert providers.auth_header(GITHUB, "t", None) == "Bearer t"
    basic = providers.auth_header(JIRA_CLOUD, "t", "me@acme.com").removeprefix("Basic ")
    assert base64.b64decode(basic) == b"me@acme.com:t"
    assert providers.auth_header(JIRA_DC, "t", None) == "Bearer t"
    with pytest.raises(providers.TokenRejected):
        providers.auth_header(BB_CLOUD, "t", None)  # needs the account email


def test_github_verify_reads_expiry_and_refuses_classic_tokens():
    t, seen = transport(
        {
            ("GET", "/user"): httpx.Response(
                200,
                json={"login": "octo", "name": "Octo Cat"},
                headers={"GitHub-Authentication-Token-Expiration": "2026-12-31 12:00:00 UTC"},
            )
        }
    )
    account = providers.verify(GITHUB, PAT, None, t)
    assert (account.account, account.display, account.expires_at) == (
        "octo",
        "Octo Cat",
        date(2026, 12, 31),
    )
    assert seen[0].headers["Authorization"] == f"Bearer {PAT}"
    with pytest.raises(providers.TokenRejected, match="fine-grained"):
        providers.verify(GITHUB, "ghp_classictoken", None, t)


@pytest.mark.parametrize(
    ("conn", "path", "body", "account"),
    [
        (JIRA_CLOUD, "/rest/api/3/myself", {"accountId": "557", "displayName": "Dev"}, "557"),
        (JIRA_DC, "/rest/api/2/myself", {"name": "dev", "displayName": "Dev"}, "dev"),
        (CONF_CLOUD, "/wiki/rest/api/user/current", {"type": "known", "accountId": "557"}, "557"),
        (BB_CLOUD, "/2.0/user", {"account_id": "557", "display_name": "Dev"}, "557"),
    ],
)
def test_verify_per_provider(conn, path, body, account):
    t, _ = transport({("GET", path): httpx.Response(200, json=body)})
    assert providers.verify(conn, "tok", "dev@acme.com", t).account == account


def test_verify_rejects_anonymous_and_refused_tokens():
    t, _ = transport(
        {("GET", "/wiki/rest/api/user/current"): httpx.Response(200, json={"type": "anonymous"})}
    )
    with pytest.raises(providers.TokenRejected, match="anonymous"):
        providers.verify(CONF_CLOUD, "tok", "dev@acme.com", t)
    t, _ = transport({("GET", "/rest/api/2/myself"): httpx.Response(401)})
    with pytest.raises(providers.TokenRejected):
        providers.verify(JIRA_DC, "tok", None, t)
    with pytest.raises(providers.TokenRejected, match="malformed"):
        providers.verify(JIRA_DC, "has space", None, t)


def test_bitbucket_dc_whoami():
    t, _ = transport({("GET", "/plugins/servlet/applinks/whoami"): httpx.Response(200, text="dev")})
    assert providers.verify(BB_DC, "tok", None, t).account == "dev"


def test_tool_calls():
    adf = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Ledger down"}]}],
    }
    t, seen = transport(
        {
            ("GET", "/rest/api/3/issue/PAY-1"): httpx.Response(
                200,
                json={
                    "key": "PAY-1",
                    "fields": {"summary": "Outage", "status": {"name": "Done"}, "description": adf},
                },
            ),
            ("GET", "/repos/acme/pay/contents/docs/a b.md"): httpx.Response(200, text="# Hello"),
        }
    )
    with providers.client_for(JIRA_CLOUD, "tok", "dev@acme.com", t) as client:
        issue = providers.jira_issue(client, JIRA_CLOUD, "PAY-1")
    assert issue["description"].strip() == "Ledger down" and issue["status"] == "Done"
    assert issue["url"] == "https://acme.atlassian.net/browse/PAY-1"
    with providers.client_for(GITHUB, PAT, None, t) as client:
        f = providers.github_file(client, GITHUB, "acme/pay", "docs/a b.md", "main")
    assert f["content"] == "# Hello"
    assert f["url"] == "https://github.com/acme/pay/blob/main/docs/a%20b.md"
    with pytest.raises(ValueError):
        providers.jira_issue(None, JIRA_CLOUD, "pay-1; drop")
    with pytest.raises(ValueError):
        providers.github_file(None, GITHUB, "acme/pay", "../../etc/passwd", "")


def test_clients_only_reach_the_connection_host():
    t, seen = transport({})
    with providers.client_for(GITHUB, PAT, None, t) as client, pytest.raises(HostNotAllowed):
        client.request("GET", "https://evil.example.com/x")
    assert seen == []


# --- service --------------------------------------------------------------------------------------


class Snap:
    def __init__(self, *conns):
        self.connections = {c.id: c for c in conns}


def service(store=None, verify=None, conns=(GITHUB, JIRA_CLOUD, JIRA_DC)):
    def default_verify(conn, token, username):
        if token == "bad":  # noqa: S105
            raise providers.TokenRejected("refused")
        return providers.Account("acct", "Account", None)

    return ConnectionService(
        store or MemoryUserStore(), lambda: Snap(*conns), verify=verify or default_verify
    )


async def test_connect_then_credential_and_status():
    svc = service()
    expires = TODAY + timedelta(days=30)
    secret = "atl-secret-0123"  # noqa: S105 (test value)
    result = await svc.connect(OID, "jira-cloud", f" {secret} ", "dev@acme.com", expires)
    assert result["connected"] and "token" not in result
    cred = await svc.credential(OID, "jira-cloud")
    assert (cred.token, cred.username) == (secret, "dev@acme.com") and secret not in repr(cred)
    status = {s["id"]: s for s in await svc.status(OID)}
    assert status["jira-cloud"]["connected"] and not status["github"]["connected"]
    assert all("token" not in s for s in status.values())
    with pytest.raises(NotConnected, match="not connected"):
        await svc.credential(OTHER, "jira-cloud")  # another user has nothing


@pytest.mark.parametrize(
    ("connection", "token", "username", "expires", "message"),
    [
        ("jira-cloud", "tok", None, TODAY + timedelta(days=5), "account email"),
        ("jira-dc", "tok", None, None, "expiry date"),
        ("jira-dc", "tok", None, TODAY - timedelta(days=1), "already expired"),
        ("jira-dc", "tok", None, TODAY + timedelta(days=200), "within 90 days"),
        ("jira-dc", "bad", None, TODAY + timedelta(days=5), "refused"),
        ("nope", "tok", None, TODAY + timedelta(days=5), "unknown connection"),
    ],
)
async def test_connect_rules(connection, token, username, expires, message):
    with pytest.raises(ConnectError, match=message):
        await service().connect(OID, connection, token, username, expires)


async def test_provider_expiry_wins_and_is_capped():
    def github_verify(conn, token, username):
        return providers.Account("octo", "Octo", TODAY + timedelta(days=400))

    svc = service(verify=github_verify)
    with pytest.raises(ConnectError, match="within 90 days"):
        await svc.connect(OID, "github", PAT, None, TODAY + timedelta(days=10))


async def test_expired_and_invalid_tokens_are_not_connected():
    store = MemoryUserStore()
    stale = replace(entry(token="old"), expires_at=(TODAY - timedelta(days=1)).isoformat())
    store.save(UserDirectory(OID, {"jira-dc": stale}))
    svc = service(store)
    with pytest.raises(NotConnected, match="expired"):
        await svc.credential(OID, "jira-dc")
    await svc.connect(OID, "jira-dc", "new", None, TODAY + timedelta(days=10))
    assert (await svc.credential(OID, "jira-dc")).token == "new"  # noqa: S105
    await svc.mark_invalid(OID, "jira-dc")
    with pytest.raises(NotConnected, match="rejected"):
        await svc.credential(OID, "jira-dc")


async def test_concurrent_connects_for_one_user_both_survive():
    class SlowStore(MemoryUserStore):
        def save(self, directory):  # widen the read-modify-write window
            import time

            time.sleep(0.05)
            super().save(directory)

    store = SlowStore()
    svc = service(store)
    expires = TODAY + timedelta(days=10)
    await asyncio.gather(
        svc.connect(OID, "jira-dc", "a", None, expires),
        svc.connect(OID, "jira-cloud", "b", "dev@acme.com", expires),
    )
    assert set(store.load(OID).connections) == {"jira-dc", "jira-cloud"}


async def test_disconnect_removes_and_deletes_empty_directories():
    store = MemoryUserStore()
    svc = service(store)
    await svc.connect(OID, "jira-dc", "a", None, TODAY + timedelta(days=10))
    assert await svc.disconnect(OID, "jira-dc")
    assert store.load(OID) is None and not await svc.disconnect(OID, "jira-dc")
    with pytest.raises(NotConnected):
        await svc.credential(OID, "jira-dc")


def test_bitbucket_cloud_401_explains_the_token_requirements():
    t, _ = transport({("GET", "/2.0/user"): httpx.Response(401)})
    with pytest.raises(providers.TokenRejected) as exc:
        providers.verify(BB_CLOUD, "tok", "dev@acme.com", t)
    message = str(exc.value)
    assert "WITH SCOPES" in message and "read:user:bitbucket" in message
    assert "Atlassian account email" in message and "tok" not in message.replace("token", "")
