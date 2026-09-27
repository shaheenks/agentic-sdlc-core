"""sdlc-db CLI: `migrate` (as sdlc_owner)."""

import argparse
import sys
from pathlib import Path

from sdlc_db.connect import conninfo
from sdlc_db.migrate import DEFAULT_DIR, migrate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdlc-db")
    sub = parser.add_subparsers(dest="command", required=True)
    mig = sub.add_parser("migrate", help="apply pending SQL migrations as sdlc_owner")
    mig.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)

    applied = migrate(conninfo("owner"), args.dir)
    print(f"applied: {', '.join(applied)}" if applied else "database is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
