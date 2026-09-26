"""sdlc-config CLI. Stage 2: validate. (compile/explain/diff arrive in Stage 3.)"""

import argparse
import sys
from pathlib import Path

from sdlc_config.errors import ConfigError
from sdlc_config.loader import load_snapshot
from sdlc_config.store import DEFAULT_CONFIG_DIR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdlc-config")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate config for one environment")
    validate.add_argument("--env", default="local")
    validate.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    validate.add_argument(
        "--dummy-env",
        action="store_true",
        help="substitute a placeholder for unset ${VAR}s (structure-only check, e.g. in CI)",
    )
    args = parser.parse_args(argv)

    try:
        snap = load_snapshot(args.config_dir, args.env, dummy_env=args.dummy_env)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    print(
        f"OK env={snap.env} version={snap.version} "
        f"groups={len(snap.groups.alias_by_id)} tenant={snap.platform.tenant_id}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
