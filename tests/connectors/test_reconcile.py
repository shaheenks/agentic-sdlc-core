"""version-02 N3: reconcile stored connections (blocked users, expired, rejected, removed)."""

import base64
from datetime import UTC, datetime, timedelta

import httpx
from cryptography.fernet import Fernet
from sdlc_config.model import ConnectionDef
from sdlc_connectors.reconcile import INVALID_GRACE_DAYS, reason_to_remove, reconcile
from sdlc_connectors.service import ConnectionService
from sdlc_connectors.user_store import (
    ConnectionEntry,
    FileUserStore,
    GcpUserStore,
    MemoryUserStore,
    UserDirectory,
    user_key,
)

from tests.connectors.test_user_connections import FakeSecretManager

ALICE = "aaaaaaaa-0000-0000-0000-00000000000a"
BOB = "bbbbbbbb-0000-0000-0000-00000000000b"
CAROL = "cccccccc-0000-0000-0000-00000000000c"
TOKEN = "github_pat_reconcile_secret"  # noqa: S105 (test value)
NOW = datetime.now(UTC)
TODAY = NOW.date()
GITHUB = ConnectionDef("github", "github", "cloud", "https://api.github.com")
JIRA = ConnectionDef("jira", "jira", "cloud", "https://acme.atlassian.net")


def entry(days_left=30, status="ok", verified_days_ago=0):
    verified = (NOW - timedelta(days=verified_days_ago)).isoformat(timespec="seconds")
    return ConnectionEntry(
        token=TOKEN,
        account="octo",
        display="Octo",
        connected_at=verified,
        verified_at=verified,
        expires_at=(TODAY + timedelta(days=days_left)).isoformat(),
        status=status,
    )


class Snap:
    def __init__(self, *conns):
        self.connections = {c.id: c for c in conns}


def service(store, *conns):
    return ConnectionService(store, lambda: Snap(*(conns or (GITHUB, JIRA))))


def test_rules():
    configured = {"github": GITHUB}
    assert reason_to_remove("github", entry(), configured, TODAY) is None
    assert reason_to_remove("github", entry(days_left=-1), configured, TODAY) == "expired"
    assert reason_to_remove("github", entry(days_left=0), configured, TODAY) is None  # last day
    assert reason_to_remove("gone", entry(), configured, TODAY) == "not_configured"
    recent = entry(status="invalid", verified_days_ago=INVALID_GRACE_DAYS - 1)
    old = entry(status="invalid", verified_days_ago=INVALID_GRACE_DAYS + 1)
    assert reason_to_remove("github", recent, configured, TODAY) is None  # page still explains
    assert reason_to_remove("github", old, configured, TODAY) == "rejected"


def seeded_store():
    store = MemoryUserStore()
    store.save(UserDirectory(ALICE, {"github": entry(), "jira": entry(days_left=-3)}))
    store.save(UserDirectory(BOB, {"github": entry()}))  # blocked below
    store.save(UserDirectory(CAROL, {"github": entry(days_left=-1)}))  # only an expired one
    return store


async def test_dry_run_reports_and_changes_nothing():
    store = seeded_store()
    before = dict(store.data)
    report = await reconcile(service(store), {BOB: "offboarded"}, today=TODAY, dry_run=True)
    assert store.data == before
    assert not report.applied and report.users == 3 and not report.errors
    got = {(c.oid, c.action, c.reason, c.connection) for c in report.changes}
    assert got == {
        (ALICE, "remove_connection", "expired", "jira"),
        (BOB, "forget_user", "blocked", ""),
        (CAROL, "remove_connection", "expired", "github"),
    }


async def test_apply_removes_deletes_and_audits():
    store = seeded_store()
    audited = []
    report = await reconcile(
        service(store), {BOB: "offboarded"}, today=TODAY, dry_run=False, audit=audited.append
    )
    assert report.applied and len(report.changes) == 3 and audited == report.changes
    assert set(store.load(ALICE).connections) == {"github"}  # the valid one stays
    assert store.load(BOB) is None  # blocked: whole directory gone
    assert store.load(CAROL) is None  # nothing left: directory deleted
    assert TOKEN not in report.summary() and TOKEN not in repr(report.changes)


async def test_reconnected_token_is_kept():
    """A removal is decided again on a fresh read under the user's lock."""
    store = MemoryUserStore()
    store.save(UserDirectory(ALICE, {"github": entry(days_left=-1)}))
    svc = service(store)
    original_scan = store.scan

    def scan_then_reconnect():
        for item in original_scan():
            store.save(UserDirectory(ALICE, {"github": entry(days_left=60)}))  # user reconnects
            yield item

    store.scan = scan_then_reconnect
    report = await reconcile(svc, {}, today=TODAY, dry_run=False)
    assert report.changes == []
    assert store.load(ALICE).connections["github"].expires_at == (
        (TODAY + timedelta(days=60)).isoformat()
    )


async def test_unreadable_and_swapped_entries_are_reported_not_trusted():
    store = MemoryUserStore()
    store.save(UserDirectory(ALICE, {"github": entry()}))
    store.data[user_key(BOB)] = store.data[user_key(ALICE)]  # ALICE's directory under BOB's name
    store.data["f" * 32] = b"not json"
    report = await reconcile(service(store), {BOB: "x"}, today=TODAY, dry_run=False)
    assert report.users == 1 and len(report.errors) == 2
    assert all("owner does not match" in e or "unreadable" in e for e in report.errors)
    assert store.load(ALICE) is not None  # the swapped copy did not trigger BOB's block


def test_file_store_scan(tmp_path):
    store = FileUserStore(tmp_path, Fernet.generate_key().decode())
    store.save(UserDirectory(ALICE, {"github": entry()}))
    (tmp_path / ("0" * 32 + ".bin")).write_bytes(b"garbage")
    items = list(store.scan())
    assert [i.directory.oid for i in items if i.directory] == [ALICE]
    assert any("cannot be decrypted" in (i.error or "") for i in items)


class ListingSecretManager(FakeSecretManager):
    """Adds secrets.list (by label filter, paged one per page)."""

    def __init__(self):
        super().__init__()
        self.filters = []

    def handler(self, request):
        prefix = "/v1/projects/proj/secrets"
        if request.method == "GET" and request.url.path == prefix:
            self.filters.append(request.url.params["filter"])
            names = sorted(self.versions)
            start = int(request.url.params.get("pageToken", "0"))
            page = names[start : start + 1]
            body = {"secrets": [{"name": f"projects/proj/secrets/{n}"} for n in page]}
            if start + 1 < len(names):
                body["nextPageToken"] = str(start + 1)
            return httpx.Response(200, json=body)
        return super().handler(request)


def test_gcp_store_scan_lists_by_label_and_pages():
    fake = ListingSecretManager()
    store = GcpUserStore(
        "proj",
        "dev",
        token_provider=lambda: "ya29.test",
        transport=httpx.MockTransport(fake.handler),
    )
    store.save(UserDirectory(ALICE, {"github": entry()}))
    store.save(UserDirectory(BOB, {"github": entry()}))
    fake.versions["unrelated-secret"] = [base64.b64encode(b"x")]  # another prefix: skipped
    oids = sorted(i.directory.oid for i in store.scan() if i.directory)
    assert oids == [ALICE, BOB]
    assert fake.filters[0] == "labels.kind=user-connections AND labels.env=dev"
    assert len(fake.filters) == 3  # paged
