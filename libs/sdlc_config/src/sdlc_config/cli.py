"""sdlc-config CLI.

  validate  check config for one environment (schemas + cross-references)
  explain   effective permissions of a persona or a set of group aliases / app roles
  diff      per-persona permission changes between two git revisions (for PR review / CI)

(`compile` arrives in Stage 7.)
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

    explain = sub.add_parser("explain", help="effective permissions of a persona")
    common(explain)
    who = explain.add_mutually_exclusive_group(required=True)
    who.add_argument("--persona", help="name from the personas file")
    who.add_argument("--groups", help="comma-separated group aliases")
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

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return _validate(args)
        if args.command == "explain":
            return _explain(args)
        return _diff(args)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1


def _validate(args) -> int:
    snap = load_snapshot(args.config_dir, args.env, dummy_env=args.dummy_env)
    print(
        f"OK env={snap.env} version={snap.version} groups={len(snap.groups.alias_by_id)} "
        f"roles={len(snap.roles)} teams={len(snap.teams)} tools={len(snap.tools)} "
        f"tenant={snap.platform.tenant_id}"
    )
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
        persona = Persona("(ad hoc)", _split(args.groups), _split(args.app_roles))
    known = set(snap.groups.alias_by_id.values())
    unknown = sorted(set(persona.groups) - known)
    policy = resolve(snap, [g for g in persona.groups if g in known], persona.app_roles)
    if args.json:
        view = policy.explain()
        view["persona"], view["unknown_groups"] = persona.name, unknown
        print(json.dumps(view, indent=2))
        return 0
    print(_render(persona, policy, unknown))
    return 0


def _render(persona: Persona, policy: EffectivePolicy, unknown: list[str]) -> str:
    lines = [
        f"persona: {persona.name}  groups: {', '.join(persona.groups) or '-'}  "
        f"app roles: {', '.join(persona.app_roles) or '-'}",
        f"config:  {policy.config_version}",
    ]
    if unknown:
        lines.append(f"unknown groups (ignored): {', '.join(unknown)}")
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
            _summary(resolve(snaps[rev], persona.groups, persona.app_roles))
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
