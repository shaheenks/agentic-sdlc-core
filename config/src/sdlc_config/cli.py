"""sdlc-config: validate, publish and activate the declared configuration.

    sdlc-config validate --env local
    sdlc-config publish  --env local --to .data/config [--activate]
    sdlc-config activate --env dev --to gs://<config bucket> --version <version>
    sdlc-config show     --env dev --to gs://<config bucket>

Publishing writes an immutable bundle; only `activate` (or `publish --activate`) changes what services use,
and it records who activated which version and when (FR-CFG-003).
"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sdlc_config_store import ConfigUnavailable, make_bundle, make_pointer, parse_bundle, parse_pointer, source_from_url
from sdlc_config_store.sources import bundle_name

from sdlc_config import CONFIG_DIR, compile_config


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True, cwd=CONFIG_DIR).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _compile(args) -> dict | None:
    compiled = compile_config(args.dir, args.env)
    for warning in compiled.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for problem in compiled.problems:
        print(f"error: {problem}", file=sys.stderr)
    return compiled.config if compiled.ok else None


def cmd_validate(args) -> int:
    config = _compile(args)
    if config is None:
        return 1
    print(
        f"config ok for env {args.env}: {len(config['surfaces'])} surfaces, {len(config['tool_groups'])} tool groups, "
        f"{len(config['grants'])} grants, {len(config['teams'])} teams"
    )
    return 0


def _activate(source, env: str, version: str, by: str) -> None:
    parse_bundle(source.read(bundle_name(version)), version, env)  # never point at a bundle that does not verify
    try:
        previous = parse_pointer(source.read_active()[0])["version"]
    except (OSError, ConfigUnavailable):
        previous = None
    now = datetime.now(UTC)
    pointer = json.dumps(make_pointer(version, by, previous, now), indent=2).encode()
    source.write(f"activations/{now.strftime('%Y%m%dT%H%M%S%fZ')}-{version}.json", pointer)
    source.write("active.json", pointer)
    record = {"log_type": "sdlc_audit", "event": "config.activate", "env": env, "version": version}
    print(json.dumps({**record, "previous": previous, "activated_by": by, "location": source.describe()}))


def _who(args) -> str:
    return args.by or _git("config", "user.name") or "unknown"


def cmd_publish(args) -> int:
    config = _compile(args)
    if config is None:
        return 1
    doc = make_bundle(args.env, config, git_sha=_git("rev-parse", "--short=12", "HEAD"))
    source = source_from_url(args.to)
    source.write(bundle_name(doc["version"]), json.dumps(doc, indent=2).encode(), if_absent=True)
    print(f"published {doc['version']} for env {args.env} to {source.describe()}")
    if args.activate:
        _activate(source, args.env, doc["version"], _who(args))
    return 0


def cmd_activate(args) -> int:
    source = source_from_url(args.to)
    try:
        _activate(source, args.env, args.version, _who(args))
    except (OSError, ConfigUnavailable) as exc:
        print(f"error: cannot activate {args.version}: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_show(args) -> int:
    source = source_from_url(args.to)
    try:
        pointer = parse_pointer(source.read_active()[0])
        bundle = parse_bundle(source.read(bundle_name(pointer["version"])), pointer["version"], args.env)
    except (OSError, ConfigUnavailable) as exc:
        print(f"error: no verified active bundle: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps({**pointer, "env": bundle.env, "created_at": bundle.created_at, "git_sha": bundle.git_sha}, indent=2)
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdlc-config")
    sub = parser.add_subparsers(dest="command", required=True)

    def command(name: str, handler, help_text: str, needs_dir: bool = True, needs_to: bool = False):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--env", required=True)
        if needs_dir:
            p.add_argument("--dir", type=Path, default=CONFIG_DIR)
        if needs_to:
            p.add_argument("--to", required=True, help="a folder, or gs://<configuration bucket>[/prefix]")
        p.set_defaults(handler=handler)
        return p

    command("validate", cmd_validate, "check every file against its schema and cross-references")
    publish = command("publish", cmd_publish, "compile and write an immutable bundle", needs_to=True)
    publish.add_argument("--activate", action="store_true", help="also make it the active version")
    publish.add_argument("--by", help="who activates (default: git user.name)")
    activate = command("activate", cmd_activate, "make a published version active", needs_dir=False, needs_to=True)
    activate.add_argument("--version", required=True)
    activate.add_argument("--by", help="who activates (default: git user.name)")
    command("show", cmd_show, "show the active version", needs_dir=False, needs_to=True)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
