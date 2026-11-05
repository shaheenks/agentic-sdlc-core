"""Reconcile users' stored connections (version-02 N3, version-01 §4.7).

Run as a job (Cloud Run job on a schedule; locally `sdlc-reconcile-connections`). It scans every
user directory in the per-user secret store and:

  - deletes the whole directory of a user on the block list (`env/<env>/blocked.yaml`);
  - removes a connection whose token has expired (`expires_at` before today);
  - removes a connection the provider rejected (`status: invalid`) more than INVALID_GRACE_DAYS
    ago, so the Connections page can still tell the user why it stopped working;
  - removes a connection that is no longer in `connections.yaml`.

There is no "not seen for N days" rule: every token must expire within the connection's
`max_token_days` (90), so expiry removes stale connections without tracking use per call.

Writes go through ConnectionService (the same per-user lock as the Connections page) and each
removal is decided again on a fresh read, so a token reconnected meanwhile is kept. `dry_run`
reports without changing anything. Unreadable entries are reported and left alone. Nothing here
prints or logs a token.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sdlc_connectors.service import ConnectionService
from sdlc_connectors.user_store import ConnectionEntry

INVALID_GRACE_DAYS = 14


@dataclass(frozen=True)
class Change:
    oid: str
    action: str  # forget_user | remove_connection
    reason: str  # blocked | expired | rejected | not_configured
    connection: str = ""  # empty for forget_user


@dataclass
class Report:
    users: int = 0
    changes: list[Change] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # "<key>: <error>" (key = hashed oid)
    applied: bool = False

    def summary(self) -> str:
        verb = "applied" if self.applied else "would apply (dry run)"
        return (
            f"reconcile: {self.users} users scanned, {len(self.changes)} changes {verb}, "
            f"{len(self.errors)} unreadable"
        )


def reason_to_remove(
    connection: str,
    entry: ConnectionEntry,
    configured: Mapping[str, object],
    today: date,
    invalid_grace_days: int = INVALID_GRACE_DAYS,
) -> str | None:
    if connection not in configured:
        return "not_configured"
    if entry.expires_at and date.fromisoformat(entry.expires_at) < today:
        return "expired"
    if entry.status != "ok":
        since = _date(entry.verified_at)
        if since is None or since < today - timedelta(days=invalid_grace_days):
            return "rejected"
    return None


def _date(value: str | None) -> date | None:
    try:
        return datetime.fromisoformat(value).date() if value else None
    except ValueError:
        return None


async def reconcile(
    service: ConnectionService,
    blocked: Mapping[str, str],
    *,
    today: date,
    dry_run: bool = True,
    audit: Callable[[Change], None] | None = None,
) -> Report:
    """`blocked`: lower-case oid -> reason (Snapshot.blocked). `audit` is called once per
    applied change."""
    report = Report(applied=not dry_run)
    configured = service.catalog()

    def decide(cid: str, entry: ConnectionEntry) -> str | None:
        return reason_to_remove(cid, entry, configured, today)

    for item in service.store.scan():
        if item.directory is None:
            report.errors.append(f"{item.key}: {item.error}")
            continue
        report.users += 1
        oid = item.directory.oid
        if oid.lower() in blocked:
            change = Change(oid, "forget_user", "blocked")
            if not dry_run:
                await service.forget_user(oid)
                if audit:
                    audit(change)
            report.changes.append(change)
            continue
        if dry_run:
            for cid, entry in sorted(item.directory.connections.items()):
                reason = decide(cid, entry)
                if reason:
                    report.changes.append(Change(oid, "remove_connection", reason, cid))
            continue
        for cid, reason in await service.prune(oid, decide):
            change = Change(oid, "remove_connection", reason, cid)
            report.changes.append(change)
            if audit:
                audit(change)
    return report
