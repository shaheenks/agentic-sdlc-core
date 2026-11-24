"""MkDocs hook that renders OKF concepts as readable pages.

An OKF concept keeps its title and description in frontmatter and uses top-level `#` headings for
body sections. This hook adds the title as the page's only H1, puts the description and review
status under it, and moves each body heading down one level. Pages without a `type` (index.md,
log.md) are left unchanged.
"""

import re

_HEADING = re.compile(r"^(#{1,5}) ")
_FENCE = re.compile(r"^(```|~~~)")


def on_page_markdown(markdown, page, config, files):
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
