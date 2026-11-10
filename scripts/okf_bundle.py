"""Checks and generated files for the OKF 0.2 knowledge bundle in `knowledge/`.

    uv run python scripts/okf_bundle.py lint            # conformance, conventions, traceability
    uv run python scripts/okf_bundle.py build           # rewrite index.md files + traceability.md
    uv run python scripts/okf_bundle.py build --check   # fail if a generated file is out of date
    uv run python scripts/okf_bundle.py drift --base origin/main   # code changed, concept not

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
Project conventions: knowledge/conventions.md
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import yaml

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "knowledge"
TRACE = BUNDLE / "traceability.md"
OKF_VERSION = "0.2"
RESERVED = {"index.md", "log.md"}
STATUSES = {"draft", "stable", "deprecated"}
PRIORITIES = {"must", "should", "could"}
IMPLEMENTATION = {"live", "built", "stub", "planned", "parked"}
BUILT = {"live", "built", "stub"}  # code exists, so a component must satisfy the requirement
REQ_ID = re.compile(r"^(FR|NFR)-[A-Z]+-\d{3}$")
REQ_TYPES = {"FR": "Functional Requirement", "NFR": "Non-Functional Requirement"}
REQ_DIRS = {"FR": "requirements/functional", "NFR": "requirements/non-functional"}
REQ_KEYS = ("title", "description", "area", "status", "priority", "implementation")
REQ_HEADINGS = ("# Statement", "# Acceptance criteria")
COMPONENT = "Component"
COMPONENT_KEYS = ("title", "description", "area", "status", "resource", "satisfies")
GENERATED_TYPES = {"Traceability Matrix"}  # written by `build`, never reviewed by hand
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
LOG_DATE = re.compile(r"^## (.*)$", re.MULTILINE)


class Concept(NamedTuple):
    path: Path
    meta: dict
    body: str

    @property
    def id(self) -> str:
        return "/" + self.path.relative_to(BUNDLE).with_suffix("").as_posix()


def split(path: Path) -> tuple[dict | None, str]:
    """Return (frontmatter, body); frontmatter is None when the file has none."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("frontmatter is not closed")
    meta = yaml.safe_load(text[4:end])
    if not isinstance(meta, dict):
        raise ValueError("frontmatter is not a mapping")
    return meta, text[end + 5 :]


def concepts() -> list[Concept]:
    """Every readable concept document (problems are reported by `lint`)."""
    found = []
    for path in sorted(BUNDLE.rglob("*.md")):
        if path.name in RESERVED:
            continue
        try:
            meta, body = split(path)
        except (ValueError, yaml.YAMLError):
            continue
        if meta:
            found.append(Concept(path, meta, body))
    return found


def has_offset(value: object) -> bool:
    """True for an ISO 8601 instant with an explicit UTC offset (spec: all timestamps)."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return False
    return isinstance(value, datetime) and value.tzinfo is not None


def target(path: Path, ref: str) -> Path | None:
    """Resolve a link or path-valued field to a file; None for URLs and anchors."""
    ref = ref.split("#", 1)[0]
    if not ref or "://" in ref or ref.startswith("mailto:"):
        return None
    found = BUNDLE / ref.lstrip("/") if ref.startswith("/") else path.parent / ref
    return found.resolve()


def check_concept(path: Path, meta: dict | None, body: str) -> list[str]:
    if meta is None or not str(meta.get("type") or "").strip():
        return ["concept needs frontmatter with a non-empty `type`"]
    errors = []
    if "status" in meta and meta["status"] not in STATUSES:
        errors.append(f"status must be one of {sorted(STATUSES)}")
    generated = meta.get("generated")
    if generated is not None:
        if not isinstance(generated, dict) or not generated.get("by"):
            errors.append("generated.by is required")
        elif "at" in generated and not has_offset(generated["at"]):
            errors.append("generated.at needs an ISO 8601 instant with a UTC offset")
    verified = meta.get("verified") or []
    verified = [verified] if isinstance(verified, dict) else verified
    for event in verified:
        if not event.get("by") or ("at" in event and not has_offset(event["at"])):
            errors.append("each verified entry needs `by` and an `at` with a UTC offset")
    if "stale_after" in meta and not has_offset(meta["stale_after"]):
        errors.append("stale_after needs an ISO 8601 instant with a UTC offset")
    if "timestamp" in meta:
        errors.append("`timestamp` is OKF 0.1; use generated.at")
    for source in meta.get("sources") or []:
        ref = source.get("resource") if isinstance(source, dict) else None
        if not ref:
            errors.append("each sources entry needs `resource`")
        elif (found := target(path, ref)) is not None and not found.exists():
            errors.append(f"source not found: {ref}")
    # Project convention: `stable` means a person has reviewed it.
    humans = [e for e in verified if str(e.get("by", "")).startswith("human:")]
    reviewed = meta["type"] not in GENERATED_TYPES
    if reviewed and meta.get("status", "stable") == "stable" and not humans:
        errors.append("status `stable` needs a `verified` entry by a `human:` actor")
    if match := REQ_ID.match(path.stem):
        errors += check_requirement(path, meta, body, match.group(1))
    elif "requirements" in path.relative_to(BUNDLE).parts:
        errors.append("requirement file names look like FR-AREA-001.md / NFR-AREA-001.md")
    if meta["type"] == COMPONENT:
        errors += check_component(path, meta, body)
    return errors


def check_requirement(path: Path, meta: dict, body: str, kind: str) -> list[str]:
    errors = []
    if meta["type"] != REQ_TYPES[kind]:
        errors.append(f"type must be `{REQ_TYPES[kind]}`")
    if path.parent != BUNDLE / REQ_DIRS[kind]:
        errors.append(f"belongs in {REQ_DIRS[kind]}/")
    errors += [f"missing `{key}`" for key in REQ_KEYS if not meta.get(key)]
    if meta.get("priority") not in PRIORITIES:
        errors.append(f"priority must be one of {sorted(PRIORITIES)}")
    if meta.get("implementation") not in IMPLEMENTATION:
        errors.append(f"implementation must be one of {sorted(IMPLEMENTATION)}")
    errors += [f"missing section `{h}`" for h in REQ_HEADINGS if f"\n{h}\n" not in f"\n{body}"]
    return errors


def check_component(path: Path, meta: dict, body: str) -> list[str]:
    errors = [f"missing `{key}`" for key in COMPONENT_KEYS if not meta.get(key)]
    if path.parent != BUNDLE / "components":
        errors.append("belongs in components/")
    resource = target(path, str(meta.get("resource") or ""))
    if resource is None or not resource.exists():
        errors.append(f"resource not found: {meta.get('resource')}")
    satisfies = set(meta.get("satisfies") or [])
    for ref in sorted(satisfies):
        if not REQ_ID.match(ref.rsplit("/", 1)[-1]) or not (BUNDLE / f"{ref[1:]}.md").exists():
            errors.append(f"satisfies: no such requirement {ref}")
    for ref in meta.get("verified_by") or []:
        if not (ROOT / ref).exists():
            errors.append(f"verified_by: not found in the repository: {ref}")
    # The body links are what OKF consumers follow, so they must say the same as the key.
    linked = set()
    for ref in LINK.findall(body):
        found = target(path, ref)
        if found is not None and REQ_ID.match(found.stem) and found.is_relative_to(BUNDLE):
            linked.add("/" + found.relative_to(BUNDLE).with_suffix("").as_posix())
    if linked != satisfies:
        errors.append(f"`satisfies` and the body's requirement links differ: {linked ^ satisfies}")
    return errors


def check_reserved(path: Path, meta: dict | None, body: str) -> list[str]:
    errors = []
    if path.name == "index.md":
        allowed = {"okf_version"} if path.parent == BUNDLE else set()
        if meta is not None and set(meta) - allowed:
            errors.append("index.md has no frontmatter (root: only `okf_version`)")
        if path.parent == BUNDLE and str((meta or {}).get("okf_version")) != OKF_VERSION:
            errors.append(f'root index.md must declare okf_version: "{OKF_VERSION}"')
    else:
        dates = LOG_DATE.findall(body)
        if meta is not None:
            errors.append("log.md has no frontmatter")
        if any(not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in dates):
            errors.append("log.md date headings must be `## YYYY-MM-DD`")
        elif dates != sorted(dates, reverse=True):
            errors.append("log.md entries must be newest first")
    return errors


def workspace_members() -> list[str]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return pyproject.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])


def check_coverage(everything: list[Concept]) -> list[str]:
    """Bundle-wide trace rules: built requirements and workspace members must be covered."""
    components = [c for c in everything if c.meta.get("type") == COMPONENT]
    if not components:  # the register does not exist yet
        return []
    satisfied = {ref for c in components for ref in c.meta.get("satisfies") or []}
    problems = [
        f"{c.path.relative_to(ROOT)}: implementation `{c.meta['implementation']}` but no "
        "component satisfies it"
        for c in everything
        if REQ_ID.match(c.path.stem)
        and c.meta.get("implementation") in BUILT
        and c.id not in satisfied
    ]
    resources = {target(c.path, str(c.meta.get("resource") or "")) for c in components}
    problems += [
        f"pyproject.toml: workspace member `{member}` has no component concept"
        for member in workspace_members()
        if (ROOT / member).resolve() not in resources
    ]
    return problems


def lint() -> list[str]:
    problems = []
    for path in sorted(BUNDLE.rglob("*.md")):
        try:
            meta, body = split(path)
        except (ValueError, yaml.YAMLError) as exc:
            problems.append(f"{path.relative_to(ROOT)}: {exc}")
            continue
        check = check_reserved if path.name in RESERVED else check_concept
        errors = check(path, meta, body)
        for ref in LINK.findall(body):
            if (found := target(path, ref)) is not None and not found.exists():
                errors.append(f"broken link: {ref}")
        problems += [f"{path.relative_to(ROOT)}: {e}" for e in errors]
    return problems + check_coverage(concepts()) + stale()


def label(concept: Concept) -> str:
    title = concept.meta.get("title", concept.path.stem)
    return f"{concept.path.stem}: {title}" if REQ_ID.match(concept.path.stem) else title


def render_index(folder: Path) -> str:
    """index.md: sub-sections first, then concepts grouped by `area` (or `type`)."""
    root = folder == BUNDLE
    title = "Agentic SDLC knowledge bundle" if root else folder.name.capitalize()
    lines = [f'---\nokf_version: "{OKF_VERSION}"\n---\n'] if root else []
    lines += [f"# {title}", ""]
    subfolders = [d for d in sorted(folder.iterdir()) if d.is_dir() and any(d.rglob("*.md"))]
    if subfolders:
        lines += ["## Sections", ""]
        for sub in subfolders:
            count = sum(1 for p in sub.rglob("*.md") if p.name not in RESERVED)
            noun = "concept" if count == 1 else "concepts"
            lines.append(f"- [{sub.name.capitalize()}]({sub.name}/index.md) - {count} {noun}")
        lines.append("")
    groups: dict[str, list[str]] = {}
    for concept in concepts():
        if concept.path.parent != folder:
            continue
        meta = concept.meta
        bullet = f"- [{label(concept)}]({concept.path.name}) - {meta.get('description', '')}"
        group = str(meta.get("area") or meta.get("type") or "Other")
        groups.setdefault(group, []).append(bullet.rstrip(" -"))
    for group, bullets in groups.items():
        lines += [f"## {group}", "", *bullets, ""]
    if (folder / "log.md").exists():
        lines += ["## History", "", "- [Change log](log.md)", ""]
    return "\n".join(lines)


def render_trace() -> str:
    """traceability.md: requirement -> components, component -> verification, and the gaps."""
    everything = concepts()
    requirements = [c for c in everything if REQ_ID.match(c.path.stem)]
    components = [c for c in everything if c.meta.get("type") == COMPONENT]

    def link(concept: Concept, text: str | None = None) -> str:
        return f"[{text or concept.path.stem}]({concept.path.relative_to(BUNDLE).as_posix()})"

    by_requirement = {
        r.id: [c for c in components if r.id in (c.meta.get("satisfies") or [])]
        for r in requirements
    }
    untraced = [r for r in requirements if not by_requirement[r.id]]
    untested = [c for c in components if not c.meta.get("verified_by")]
    lines = [
        "---",
        "type: Traceability Matrix",
        "title: Traceability matrix",
        "description: Which components satisfy each requirement, what verifies each component, "
        "and where the gaps are.",
        "tags: [trace]",
        "---",
        "",
        "Generated by `scripts/okf_bundle.py build` from the `satisfies` and `verified_by` keys "
        "of the component concepts. Do not edit.",
        "",
        "# Summary",
        "",
        f"- {len(requirements)} requirements, {len(requirements) - len(untraced)} satisfied by at "
        f"least one component, {len(untraced)} with none.",
        f"- {len(components)} components, {len(untested)} with no automated verification.",
        "",
        "# Requirements to components",
        "",
        "| Requirement | Priority | Code | Components |",
        "|---|---|---|---|",
    ]
    for r in requirements:
        names = ", ".join(link(c) for c in by_requirement[r.id]) or "-"
        lines.append(
            f"| {link(r)} {r.meta.get('title', '')} | {r.meta.get('priority', '')} "
            f"| {r.meta.get('implementation', '')} | {names} |"
        )
    lines += [
        "",
        "# Components to verification",
        "",
        "| Component | Code | Requirements | Verified by |",
        "|---|---|---|---|",
    ]
    for c in components:
        code = target(c.path, str(c.meta.get("resource") or ""))
        where = code.relative_to(ROOT).as_posix() if code and code.is_relative_to(ROOT) else "-"
        tests = "<br>".join(f"`{t}`" for t in c.meta.get("verified_by") or []) or "-"
        count = len(c.meta.get("satisfies") or [])
        lines.append(f"| {link(c)} | `{where}` | {count} | {tests} |")
    lines += ["", "# Gaps", "", "## Requirements no component satisfies", ""]
    lines += [
        f"- {link(r)} {r.meta.get('title', '')} ({r.meta.get('implementation', '')})"
        for r in untraced
    ] or ["None."]
    lines += ["", "## Components with no automated verification", ""]
    lines += [f"- {link(c)}" for c in untested] or ["None."]
    return "\n".join(lines) + "\n"


def generated_files() -> dict[Path, str]:
    folders = [BUNDLE, *(d for d in sorted(BUNDLE.rglob("*")) if d.is_dir())]
    files = {f / "index.md": render_index(f) for f in folders if any(f.rglob("*.md"))}
    if any(c.meta.get("type") == COMPONENT for c in concepts()):
        files[TRACE] = render_trace()
    return files


def stale() -> list[str]:
    return [
        f"{path.relative_to(ROOT)}: out of date (run `okf_bundle.py build`)"
        for path, text in generated_files().items()
        if not path.exists() or path.read_text(encoding="utf-8") != text
    ]


def drift(base: str) -> list[str]:
    """Components whose code changed since `base` while their concept did not (a review hint)."""
    git = shutil.which("git")
    if git is None:
        return ["git not found"]
    out = subprocess.run(  # noqa: S603 (fixed git command, rev passed as one argument)
        [git, "diff", "--name-only", f"{base}...HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    changed = [ROOT / line for line in out.stdout.splitlines() if line]
    hints = []
    for concept in concepts():
        code = target(concept.path, str(concept.meta.get("resource") or ""))
        if concept.meta.get("type") != COMPONENT or code is None or concept.path in changed:
            continue
        touched = [p for p in changed if p == code or code in p.parents]
        if touched:
            where = concept.path.relative_to(ROOT).as_posix()
            hints.append(
                f"{code.relative_to(ROOT).as_posix()}: {len(touched)} file(s) changed, "
                f"{where} did not"
            )
    return hints


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("lint")
    commands.add_parser("build").add_argument("--check", action="store_true")
    commands.add_parser("drift").add_argument("--base", default="origin/main")
    args = parser.parse_args()
    if args.command == "build" and not args.check:
        # Twice: the root index lists traceability.md, which the first pass may create.
        for _ in range(2):
            for path, text in generated_files().items():
                path.write_text(text, encoding="utf-8", newline="\n")
        return 0
    if args.command == "drift":
        hints = drift(args.base)
        print("\n".join(hints) or "no component changed without its concept")
        return 1 if hints else 0
    problems = lint() if args.command == "lint" else stale()
    print("\n".join(problems) or "knowledge bundle OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
