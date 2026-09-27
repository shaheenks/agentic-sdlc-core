"""sdlc-db CLI: `bootstrap` (as the admin user: extension, roles, schema, grants) and `migrate`
(as sdlc_owner). Both are idempotent."""

import argparse
import sys
from pathlib import Path

from sdlc_db.bootstrap import bootstrap
from sdlc_db.connect import conninfo
from sdlc_db.migrate import DEFAULT_DIR, migrate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdlc-db")
    sub = parser.add_subparsers(dest="command", required=True)
    mig = sub.add_parser("migrate", help="apply pending SQL migrations as sdlc_owner")
    mig.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    sub.add_parser(
        "bootstrap", help="create/update extension, roles, schema and grants (admin user)"
    )
    args = parser.parse_args(argv)

    if args.command == "bootstrap":
        created = bootstrap(conninfo("admin"))
        print(f"created: {', '.join(created)}" if created else "roles and schema are up to date")
        return 0
    applied = migrate(conninfo("owner"), args.dir)
    print(f"applied: {', '.join(applied)}" if applied else "database is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
