"""sdlc-config CLI.

validate  check config for one environment (schemas + cross-references)
explain   effective permissions of a persona or a set of group aliases / app roles / a user
users     users sync: look up (read-only) the Entra object IDs of env/<env>/users.yaml
diff      per-persona permission changes between two git revisions (for PR review / CI)
compile   validate and write an immutable bundle (optionally activate it)
activate  point a bundle root's `current` at a version (rollback = an older version)
bundles   list the bundles under a root and show the active one
"""

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

from sdlc_config.errors import ConfigError
from sdlc_config.loader import load_snapshot
from sdlc_config.personas import Persona, load_personas
from sdlc_config.resolver import EffectivePolicy, resolve
from sdlc_config.store import DEFAULT_CONFIG_DIR

DEFAULT_PERSONAS = DEFAULT_CONFIG_DIR.parent / "tests" / "policy" / "personas.yaml"
WORKTREE = "WORKTREE"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdlc-config")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--env", default="local")
        p.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
        p.add_argument(
            "--dummy-env",
            action="store_true",
            help="substitute a placeholder for unset ${VAR}s (structure-only check, e.g. in CI)",
        )

    validate = sub.add_parser("validate", help="validate config for one environment")
    common(validate)
    validate.add_argument(
        "--check-secrets",
        action="store_true",
        help="also check that every secret reference resolves (values are never printed; "
        "uses SDLC_SECRETS_BACKEND, so set gcp + SDLC_SECRETS_PROJECT to check Secret Manager)",
    )

    explain = sub.add_parser("explain", help="effective permissions of a persona")
    common(explain)
    who = explain.add_mutually_exclusive_group(required=True)
    who.add_argument("--persona", help="name from the personas file")
    who.add_argument("--groups", help="comma-separated group aliases")
    who.add_argument("--user", help="users.yaml alias (add --groups via a persona if needed)")
    explain.add_argument("--app-roles", default="", help="comma-separated Entra app roles")
    explain.add_argument("--personas", type=Path, default=DEFAULT_PERSONAS)
    explain.add_argument("--json", action="store_true", help="machine-readable output")

    diff = sub.add_parser("diff", help="per-persona permission changes between git revisions")
    diff.add_argument("--env", default="local")
    diff.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    diff.add_argument("--from", dest="rev_from", default="HEAD", help="git revision (default HEAD)")
    diff.add_argument(
        "--to",
        dest="rev_to",
        default=WORKTREE,
        help="git revision or WORKTREE (default: working tree)",
    )
    diff.add_argument("--personas", type=Path, default=DEFAULT_PERSONAS)
    diff.add_argument("--exit-code", action="store_true", help="exit 1 if permissions changed")

    comp = sub.add_parser("compile", help="write an immutable config bundle")
    common(comp)
    comp.add_argument("--out", type=Path, required=True, help="bundle root")
    comp.add_argument("--activate", action="store_true", help="point `current` at the bundle")

    act = sub.add_parser("activate", help="point the bundle root's `current` at a version")
    act.add_argument("version")
    act.add_argument("--root", type=Path, required=True)
    act.add_argument("--env", help="refuse a bundle compiled for another environment")

    ls = sub.add_parser("bundles", help="list bundles; * marks the active one")
    ls.add_argument("--root", type=Path, required=True)

    users = sub.add_parser("users", help="direct members (env/<env>/users.yaml)")
    users_sub = users.add_subparsers(dest="users_command", required=True)
    sync = users_sub.add_parser(
        "sync", help="look up missing object IDs by email in Entra (read-only, via az)"
    )
    sync.add_argument("--env", default="local")
    sync.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    sync.add_argument("--write", action="store_true", help="save found object IDs to users.yaml")
    sync.add_argument(
        "--check", action="store_true", help="also re-check existing object IDs against the emails"
    )

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return _validate(args)
        if args.command == "explain":
            return _explain(args)
        if args.command in ("compile", "activate", "bundles"):
            return _bundle_command(args)
        if args.command == "users":
            return _users(args)
        return _diff(args)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1


def _validate(args) -> int:
    snap = load_snapshot(args.config_dir, args.env, dummy_env=args.dummy_env)
    print(
        f"OK env={snap.env} version={snap.version} groups={len(snap.groups.alias_by_id)} "
        f"roles={len(snap.roles)} teams={len(snap.teams)} tools={len(snap.tools)} "
        f"users={len(snap.users.alias_by_oid)} tenant={snap.platform.tenant_id}"
    )
    if snap.users.pending:
        print(
            f"warning: users without an oid get no access: {', '.join(snap.users.pending)} "
            f"(run: sdlc-config users sync --env {snap.env} --write)"
        )
    if getattr(args, "check_secrets", False):
        return _check_secrets(snap)
    return 0


def secret_references(snap) -> dict[tuple[str, str], list[str]]:
    """(kind, name) -> where it is used. Sources' `spec.credentials` are the only references in
    config today; user connections are per-user tokens and are not config."""
    refs: dict[tuple[str, str], list[str]] = {}
    for source in sorted(snap.sources.values(), key=lambda s: s.id):
        if source.credentials:
            refs.setdefault(source.credentials, []).append(f"sources/{source.id}.yaml")
    return refs


def _check_secrets(snap, resolver=None) -> int:
    """Resolve each reference once; print only names and outcomes (never values)."""
    from sdlc_secrets import SecretAccessDenied, SecretError, SecretNotFound, resolver_from_env

    refs = secret_references(snap)
    if not refs:
        print("secrets: no secret references in config")
        return 0
    try:
        resolver = resolver or resolver_from_env()
    except SecretError as e:
        print(f"secrets: cannot create the resolver: {e}", file=sys.stderr)
        return 1
    failed = 0
    for (kind, name), used_by in sorted(refs.items()):
        try:
            resolver.resolve((kind, name))
            outcome = "ok"
        except SecretNotFound:
            outcome, failed = "MISSING", failed + 1
        except SecretAccessDenied:
            outcome, failed = "ACCESS DENIED", failed + 1
        except SecretError as e:
            outcome, failed = f"ERROR ({type(e).__name__})", failed + 1
        print(f"secrets: {kind}:{name} {outcome} (used by {', '.join(used_by)})")
    print(f"secrets: {len(refs) - failed}/{len(refs)} resolve (backend {resolver.store.name})")
    return 1 if failed else 0


def _users(args) -> int:
    from sdlc_config.users import az_runner, sync

    path = args.config_dir / "env" / args.env / "users.yaml"
    lines, problems = sync(path, az_runner(), write=args.write, check=args.check)
    print("\n".join(lines))
    if not args.write and any(" (not saved)" in line for line in lines):
        print("re-run with --write to save the object IDs")
    return 1 if problems else 0


def _bundle_command(args) -> int:
    from sdlc_config import bundles

    if args.command == "compile":
        version, created = bundles.compile_bundle(
            args.config_dir, args.env, args.out, dummy_env=args.dummy_env
        )
        print(f"{'compiled' if created else 'unchanged'} {version} -> {args.out / version}")
        if args.activate:
            bundles.activate(args.out, version, args.env)
            print(f"active: {version}")
        return 0
    if args.command == "activate":
        bundles.activate(args.root, args.version, args.env)
        print(f"active: {args.version}")
        return 0
    try:
        active = bundles.current_version(args.root)
    except ConfigError:
        active = None
    for m in bundles.list_bundles(args.root):
        mark = "*" if m["version"] == active else " "
        print(f"{mark} {m['version']}  env={m['env']}  created={m['created_at']}")
    return 0


def _split(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(",") if v.strip())


def _explain(args) -> int:
    snap = load_snapshot(args.config_dir, args.env, dummy_env=args.dummy_env)
    if args.persona:
        personas = load_personas(args.personas)
        if args.persona not in personas:
            raise ConfigError([f"unknown persona '{args.persona}' (have: {sorted(personas)})"])
        persona = personas[args.persona]
    else:
        persona = Persona(
            "(ad hoc)", _split(args.groups or ""), _split(args.app_roles), args.user or None
        )
    known = set(snap.groups.alias_by_id.values())
    unknown = sorted(set(persona.groups) - known)
    if persona.user and persona.user not in snap.users.email_by_alias:
        unknown.append(f"user:{persona.user}")
    groups = [g for g in persona.groups if g in known]
    policy = resolve(snap, groups, persona.app_roles, _known_user(snap, persona))
    if args.json:
        view = policy.explain()
        view["persona"], view["unknown_groups"] = persona.name, unknown
        print(json.dumps(view, indent=2))
        return 0
    print(_render(persona, policy, unknown))
    return 0


def _known_user(snap, persona: Persona) -> str | None:
    """The persona's users.yaml alias if this environment has it (users.yaml is per tenant)."""
    return persona.user if persona.user in snap.users.email_by_alias else None


def _render(persona: Persona, policy: EffectivePolicy, unknown: list[str]) -> str:
    lines = [
        f"persona: {persona.name}  groups: {', '.join(persona.groups) or '-'}  "
        f"app roles: {', '.join(persona.app_roles) or '-'}  user: {persona.user or '-'}",
        f"config:  {policy.config_version}",
    ]
    if unknown:
        lines.append(f"unknown groups/users (ignored): {', '.join(unknown)}")
    lines.append("teams:")
    lines += [f"  {t:<14} <- {', '.join(r)}" for t, r in sorted(policy.teams.items())] or ["  -"]
    lines.append("roles:")
    lines += [f"  {r:<14} <- {', '.join(w)}" for r, w in sorted(policy.roles.items())] or ["  -"]
    lines.append("tools:")
    for name, perm in sorted(policy.tools.items()):
        limits = (
            "; ".join(
                f"{a} in [{', '.join(sorted(v))}]" for a, v in sorted(perm.constraints.items())
            )
            if perm.constraints
            else "no limits"
        )
        lines.append(f"  {name:<18} {limits:<45} <- {perm.allowed_by[0]}")
    if not policy.tools:
        lines.append("  -")
    if policy.denied:
        lines.append("denied:")
        lines += [f"  {t:<18} <- {', '.join(r)}" for t, r in sorted(policy.denied.items())]
    return "\n".join(lines)


# --- diff ---------------------------------------------------------------------------------------


def _git() -> str:
    git = shutil.which("git")
    if not git:
        raise ConfigError(["git not found on PATH (needed for diff)"])
    return git


def _repo_root(path: Path) -> Path:
    out = subprocess.run(  # noqa: S603 (fixed git command)
        [_git(), "rev-parse", "--show-toplevel"], cwd=path, capture_output=True, text=True
    )
    if out.returncode != 0:
        raise ConfigError([f"not a git repository: {path}"])
    return Path(out.stdout.strip())


def _config_at(rev: str, config_dir: Path, env: str, workdir: Path) -> Path:
    """Materialize config/ (and the sibling skills/, which config references) at a git revision.
    groups.yaml is git-ignored, so the working tree's (or the committed example) is used: diffs
    compare policy, not tenant group IDs."""
    if rev == WORKTREE:
        return config_dir
    repo = _repo_root(config_dir)
    rel = config_dir.resolve().relative_to(repo.resolve()).as_posix()
    skills_rel = (config_dir.parent / "skills").resolve().relative_to(repo.resolve()).as_posix()
    out = None
    for paths in ([rel, skills_rel], [rel]):  # older revisions may have no skills/ folder
        out = subprocess.run(  # noqa: S603 (fixed git command, rev passed as one argument)
            [_git(), "archive", "--format=tar", rev, *paths], cwd=repo, capture_output=True
        )
        if out.returncode == 0:
            break
    if out.returncode != 0:
        raise ConfigError([f"git archive {rev}: {out.stderr.decode(errors='replace').strip()}"])
    target = workdir / rev.replace("/", "_")
    with tarfile.open(fileobj=BytesIO(out.stdout)) as tar:
        tar.extractall(target, filter="data")
    at_rev = target / rel
    groups = at_rev / "env" / env / "groups.yaml"
    if not groups.exists():
        source = config_dir / "env" / env / "groups.yaml"
        if not source.exists():
            source = config_dir / "env" / env / "groups.yaml.example"
        groups.parent.mkdir(parents=True, exist_ok=True)
        groups.write_bytes(source.read_bytes())
    users = config_dir / "env" / env / "users.yaml"  # git-ignored too; optional
    knows_users = (at_rev / "schemas" / "usermap.schema.json").exists()  # version-02 N10+
    if users.exists() and knows_users and not (at_rev / "env" / env / "users.yaml").exists():
        (at_rev / "env" / env / "users.yaml").write_bytes(users.read_bytes())
    return at_rev


def _summary(policy: EffectivePolicy) -> dict[str, str]:
    """tool -> printable limits and skill:<name> -> visibility, for comparing two policies."""
    result = {}
    for name, perm in policy.tools.items():
        if perm.constraints:
            result[name] = "; ".join(
                f"{a} in [{', '.join(sorted(v))}]" for a, v in sorted(perm.constraints.items())
            )
        else:
            result[name] = "no limits"
    for name, grant in policy.skills.items():
        result[f"skill:{name}"] = f"team add-on ({grant.team})" if grant.team else "global"
    for item in policy.agent_instructions:
        result[f"instructions:{item.team}"] = item.source
    return result


def _diff(args) -> int:
    personas = load_personas(args.personas)
    with tempfile.TemporaryDirectory() as tmp:
        snaps = {}
        for rev in (args.rev_from, args.rev_to):
            config_dir = _config_at(rev, args.config_dir, args.env, Path(tmp))
            snaps[rev] = load_snapshot(config_dir, args.env, dummy_env=True)
    changed = False
    print(f"permission diff {args.rev_from} -> {args.rev_to} (env {args.env})")
    for name, persona in personas.items():
        before, after = (
            _summary(
                resolve(
                    snaps[rev], persona.groups, persona.app_roles, _known_user(snaps[rev], persona)
                )
            )
            for rev in (args.rev_from, args.rev_to)
        )
        lines = [f"  + {t}  ({after[t]})" for t in sorted(after.keys() - before.keys())]
        lines += [f"  - {t}" for t in sorted(before.keys() - after.keys())]
        lines += [
            f"  ~ {t}  ({before[t]} -> {after[t]})"
            for t in sorted(before.keys() & after.keys())
            if before[t] != after[t]
        ]
        if lines:
            changed = True
            print(f"{name}:")
            print("\n".join(lines))
    if not changed:
        print("no permission changes")
    return 1 if changed and args.exit_code else 0


if __name__ == "__main__":
    sys.exit(main())
