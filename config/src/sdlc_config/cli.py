"""sdlc-config: validate the declared configuration."""

import argparse
import sys
from pathlib import Path

import yaml

from sdlc_config import CONFIG_DIR, load_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdlc-config")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="parse and check the configuration")
    validate.add_argument("--env", required=True)
    validate.add_argument("--dir", type=Path, default=CONFIG_DIR)
    args = parser.parse_args(argv)

    try:
        docs = load_all(args.dir, args.env)
    except yaml.YAMLError as exc:
        print(f"invalid YAML: {exc}", file=sys.stderr)
        return 1
    print(f"config ok: {len(docs)} file(s) for env {args.env}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
