"""MkDocs hook that renders OKF concepts as readable pages.

An OKF concept keeps its title and description in frontmatter and uses top-level `#` headings for
body sections. This hook adds the title as the page's only H1, puts the description and review
status under it, and moves each body heading down one level. Pages without a `type` (index.md,
log.md) are left unchanged.

The site is built from `spec/`, and this hook also adds the Markdown pages under the repository's `docs/`
folder at `docs/...`. Their links into the bundle (`../../spec/...`) are rewritten to the site's root.
"""

import re
from pathlib import Path

from mkdocs.structure.files import File

_ROOT = Path(__file__).resolve().parent.parent
_EXTRA = _ROOT / "docs"
_SPEC_LINK = re.compile(r"\]\(((?:\.\./)+)spec/")

_HEADING = re.compile(r"^(#{1,5}) ")
_FENCE = re.compile(r"^(```|~~~)")


def on_files(files, config):
    for path in sorted(_EXTRA.rglob("*.md")):
        rel = path.relative_to(_ROOT).as_posix()
        files.append(File(rel, src_dir=str(_ROOT), dest_dir=config["site_dir"],
                          use_directory_urls=config["use_directory_urls"]))
    return files


def on_page_markdown(markdown, page, config, files):
    if page.file.src_uri.startswith("docs/"):
        markdown = _SPEC_LINK.sub(lambda m: "](" + m.group(1), markdown)
    meta = page.meta or {}
    if not meta.get("type"):
        return markdown

    lines, in_fence = [], False
    for line in markdown.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and _HEADING.match(line):
            line = "#" + line
        lines.append(line)

    title = meta.get("title", page.title)
    badges = [f"`{meta['type']}`"]
    if meta.get("status"):
        badges.append(f"`status: {meta['status']}`")
    if meta.get("x-layer"):
        badges.append(f"`layer: {meta['x-layer']}`")

    header = [f"# {title}", "", " ".join(badges), ""]
    if meta.get("description"):
        header += [f"*{meta['description']}*", ""]
    return "\n".join(header + lines) + "\n"
