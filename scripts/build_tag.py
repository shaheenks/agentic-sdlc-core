"""Image tags from build inputs (CH-0024; NFR-OPS-002).

An image's tag is `src-<12 hex>`: SHA-256 of `git ls-tree -r <rev> -- <inputs>` (mode, blob id and
path of every committed input file), where the inputs are the Dockerfile, `.dockerignore` and every
`COPY`/`ADD` source (not `COPY --from`). The tag needs no build, is the same on every machine, and
changes only when one of the image's own committed inputs changes. Git-ignored files (`users.yaml`,
`blocked.yaml`) are never inputs. Uncommitted changes are not seen: gcp_deploy.ps1 refuses a dirty
tree.

    uv run python scripts/build_tag.py [--root <repo>] [--rev HEAD]

prints {terraform key: {name, dockerfile, tag}} as JSON, in IMAGES order. The image list lives here
only; gcp_deploy.ps1 (and CH-0010's bash twin) read it from this output.
"""

import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

# Terraform key (infra/gcp `var.image_tags`, `local.images`) -> (registry name, Dockerfile)
IMAGES: dict[str, tuple[str, str]] = {
    "mcp": ("core-mcp", "mcp_servers/core_mcp/Dockerfile"),
    "mcp_gcp": ("core-mcp-gcp", "mcp_servers/core_mcp_gcp/Dockerfile"),  # GCP stack (CH-0022)
    "agent": ("user-agent", "agents/user_agent/Dockerfile"),
    "ingest": ("ingest", "ingest/bootstrap/Dockerfile"),
    "ui": ("ui-copilotkit", "ui/copilotkit/Dockerfile"),  # chat app (version-01 M5)
}
DOCKERIGNORE = ".dockerignore"


class BuildTagError(Exception):
    pass


def _normal(path: str) -> str:
    path = path.removeprefix("./").rstrip("/")
    return path or "."


def copy_sources(dockerfile_text: str) -> list[str]:
    """Build-context paths copied by COPY/ADD; `--from` copies come from another image."""
    sources: list[str] = []
    for line in dockerfile_text.splitlines():
        first = line.split(maxsplit=1)
        if not first or first[0].upper() not in ("COPY", "ADD"):
            continue  # only COPY/ADD are parsed (RUN lines may hold shell escapes)
        words = shlex.split(line, comments=True, posix=True)
        args = words[1:]
        if any(a.startswith("--from") for a in args):
            continue
        paths = [a for a in args if not a.startswith("--")]
        sources += [_normal(p) for p in paths[:-1]]  # the last one is the destination
    return sources


def inputs(root: Path, dockerfile: str) -> list[str]:
    text = (Path(root) / dockerfile).read_text(encoding="utf-8")
    return sorted({_normal(dockerfile), DOCKERIGNORE, *copy_sources(text)})


def _ls_tree(root: Path, rev: str, paths: list[str]) -> bytes:
    git_exe = shutil.which("git") or "git"
    result = subprocess.run(  # noqa: S603 (fixed read-only git command)
        [git_exe, "-C", str(root), "ls-tree", "-r", "--full-tree", rev, "--", *paths],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise BuildTagError(f"git ls-tree failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def build_tag(root: Path, dockerfile: str, rev: str = "HEAD") -> str:
    paths = inputs(root, dockerfile)
    listing = _ls_tree(root, rev, paths)
    committed = [line.split(b"\t", 1)[1].decode() for line in listing.splitlines()]
    for path in paths:
        if path == DOCKERIGNORE and not (Path(root) / DOCKERIGNORE).exists():
            continue  # optional
        if not any(c == path or c.startswith(f"{path}/") for c in committed):
            raise BuildTagError(f"{dockerfile} copies {path}, which is not committed at {rev}")
    return "src-" + hashlib.sha256(listing).hexdigest()[:12]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--rev", default="HEAD")
    args = parser.parse_args(argv)
    try:
        out = {
            key: {
                "name": name,
                "dockerfile": dockerfile,
                "tag": build_tag(args.root, dockerfile, args.rev),
            }
            for key, (name, dockerfile) in IMAGES.items()
        }
    except (BuildTagError, OSError) as e:
        print(f"build_tag: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
