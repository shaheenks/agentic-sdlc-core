"""sdlc-reconcile-connections: clean up users' stored connections (version-02 N3).

    sdlc-reconcile-connections            dry run: report what would change (default)
    sdlc-reconcile-connections --apply    delete / remove, audited as `connection_change`

Same environment as the MCP server (it owns the per-user secret store): config via ConfigStore
(bundles or folder), SDLC_USER_SECRETS_BACKEND and its settings, and PG* for the per-user advisory
lock when the database is configured. Locally: `docker compose exec core-mcp
sdlc-reconcile-connections`. On GCP: the `sdlc-reconcile-<env>` Cloud Run job. Rules:
sdlc_connectors.reconcile. Exit 1 if an entry could not be read or a change failed.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import UTC, datetime

from sdlc_config import ConfigError, ConfigStore
from sdlc_connectors.errors import ConnectorError
from sdlc_connectors.reconcile import Change, reconcile

from sdlc_core_mcp.audit import emit, new_request_id
from sdlc_core_mcp.server import build_connected, build_knowledge

log = logging.getLogger("sdlc.mcp")


def audit(change: Change) -> None:
    emit(
        {
            "event": "connection_change",
            "ts": datetime.now(UTC).isoformat(),
            "request_id": new_request_id(),
            "actor": "reconcile",
            "oid": change.oid,
            "action": change.action,
            "connection": change.connection,
            "outcome": "ok",
            "reason": change.reason,
        }
    )


async def run(apply: bool) -> int:
    store = ConfigStore.from_env()  # fail closed on invalid config
    snapshot = store.current()
    knowledge = build_knowledge(snapshot) if os.environ.get("PGHOST") else None
    connected = build_connected(store, knowledge)
    if connected.service is None:
        print("reconcile: user connections are off (SDLC_USER_SECRETS_BACKEND not set)")
        return 0
    try:
        report = await reconcile(
            connected.service,
            snapshot.blocked,
            today=datetime.now(UTC).date(),
            dry_run=not apply,
            audit=audit,
        )
    except ConnectorError as e:
        print(f"reconcile: failed: {e}", file=sys.stderr)
        return 1
    finally:
        if knowledge is not None and knowledge._opened:
            await knowledge.pool.close()
    for change in report.changes:
        what = change.connection or "all connections"
        print(f"  {change.action:<17} {change.reason:<14} {what:<12} oid={change.oid}")
    for error in report.errors:
        print(f"  unreadable: {error}")
    print(f"{report.summary()} (config {snapshot.version})")
    return 1 if report.errors else 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(message)s")
    parser = argparse.ArgumentParser(
        prog="sdlc-reconcile-connections",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="make the changes")
    mode.add_argument("--dry-run", action="store_true", help="report only (the default)")
    args = parser.parse_args(argv)
    try:  # psycopg async needs a selector loop (Windows defaults to Proactor)
        return asyncio.run(run(args.apply), loop_factory=asyncio.SelectorEventLoop)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
