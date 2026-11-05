"""`sdlc-config users sync`: fill in and check the Entra object IDs of env/<env>/users.yaml.

Admins list direct members by email; the MCP server matches tokens on `oid` only (emails can
change or be reused). This looks each email up in Entra with the Azure CLI, read-only
(`az ad user show`), as whichever account `az` is signed in as (printed first). It never writes
to Entra. With `--write` it saves found oids back to users.yaml; YAML comments other than the
file header are not kept.
"""

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import yaml

from sdlc_config.errors import ConfigError

Runner = Callable[[list[str]], tuple[int, str]]  # az arguments -> (exit code, stdout)


def az_runner() -> Runner:
    az = shutil.which("az")  # az.cmd on Windows
    if not az:
        raise ConfigError(["Azure CLI (az) not found on PATH: needed to look up user object IDs"])

    def run(args: list[str]) -> tuple[int, str]:
        out = subprocess.run(  # noqa: S603 (fixed az command; values passed as single arguments)
            [az, *args], capture_output=True, text=True
        )
        return out.returncode, out.stdout

    return run


def _lookup(run: Runner, key: str) -> dict | None:
    """Entra user by UPN/email or object ID, or None if not found."""
    code, out = run(["ad", "user", "show", "--id", key, "-o", "json"])
    if code != 0 or not out.strip():
        return None
    return json.loads(out)


def sync(
    path: Path, run: Runner, write: bool = False, check: bool = False
) -> tuple[list[str], int]:
    """Returns (report lines, problem count). Problems: an email not found, or (check) an oid
    whose account is gone or whose sign-in name no longer matches the listed email."""
    if not path.is_file():
        raise ConfigError([f"{path}: not found (copy users.yaml.example and list your users)"])
    text = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text) or {}
    users = doc.get("users") or {}
    lines, problems, changed = [], 0, False

    code, account = run(["account", "show", "--query", "user.name", "-o", "tsv"])
    lines.append(f"az signed in as: {account.strip() if code == 0 else '(not signed in)'}")

    for alias, entry in users.items():
        email = str(entry.get("email", "")).lower()
        oid = entry.get("oid")
        if not oid:
            found = _lookup(run, email)
            if found is None:
                lines.append(f"  {alias}: {email} NOT FOUND in Entra (stays pending: no access)")
                problems += 1
                continue
            entry["oid"] = found["id"]
            changed = True
            lines.append(f"  {alias}: {email} -> oid found{'' if write else ' (not saved)'}")
        elif check:
            found = _lookup(run, oid)
            names = (
                {str(found.get(k) or "").lower() for k in ("userPrincipalName", "mail")}
                if found
                else set()
            )
            if found is None:
                lines.append(f"  {alias}: oid no longer exists in Entra (remove the entry)")
                problems += 1
            elif email not in names:
                lines.append(
                    f"  {alias}: sign-in name is now {found.get('userPrincipalName')}, "
                    f"not {email} (same person? update the email or the entry)"
                )
                problems += 1
            else:
                lines.append(f"  {alias}: ok")

    if changed and write:
        header = []
        for line in text.splitlines():
            if not line.startswith("#"):
                break
            header.append(line)
        body = dump_user_map(doc)
        path.write_text("\n".join([*header, body]) if header else body, encoding="utf-8")
        lines.append(f"saved {path}")
    return lines, problems


def dump_user_map(doc: dict) -> str:
    """users.yaml with one flow-style (JSON-like) line per user, so each entry reads at a glance
    and diffs per user: `paul: {email: paul@x.com, oid: ..., teams: {sdlc-platform: [lead]}}`."""
    head = {k: v for k, v in doc.items() if k != "users"}
    out = yaml.safe_dump(head, sort_keys=False, allow_unicode=True)
    users = doc.get("users") or {}
    if not users:
        return out + "users: {}\n"
    out += "users:\n"
    for alias, entry in users.items():
        line = yaml.safe_dump(
            {alias: entry},
            default_flow_style=True,
            sort_keys=False,
            allow_unicode=True,
            width=10_000,
        ).strip()
        out += f"  {line[1:-1]}\n"  # drop the outer braces: `alias: {...}`
    return out
