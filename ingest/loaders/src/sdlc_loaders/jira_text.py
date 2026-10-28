"""Jira rich text -> Markdown (version-01 M4).

  adf_to_markdown   Atlassian Document Format (Jira Cloud REST v3: description, comments)
  wiki_to_markdown  Jira wiki markup (Jira Data Center REST v2)

Both keep headings, paragraphs, lists, code, quotes/panels, tables and links; media is dropped.
"""

import re
from collections.abc import Mapping
from typing import Any

# --- Atlassian Document Format --------------------------------------------------------------------


def _inline(nodes: list[Mapping[str, Any]] | None) -> str:
    out = []
    for node in nodes or []:
        kind = node.get("type")
        if kind == "text":
            text = node.get("text", "")
            for mark in node.get("marks") or []:
                m = mark.get("type")
                if m == "strong":
                    text = f"**{text}**"
                elif m == "em":
                    text = f"*{text}*"
                elif m == "code":
                    text = f"`{text}`"
                elif m == "strike":
                    text = f"~~{text}~~"
                elif m == "link" and (mark.get("attrs") or {}).get("href"):
                    text = f"[{text}]({mark['attrs']['href']})"
            out.append(text)
        elif kind == "hardBreak":
            out.append("\n")
        elif kind in ("mention", "emoji", "status", "date"):
            attrs = node.get("attrs") or {}
            out.append(
                str(attrs.get("text") or attrs.get("shortName") or attrs.get("timestamp", ""))
            )
        elif kind in ("inlineCard", "blockCard"):
            out.append((node.get("attrs") or {}).get("url", ""))
        elif node.get("content"):
            out.append(_inline(node.get("content")))
    return "".join(out)


def _blocks(nodes: list[Mapping[str, Any]] | None) -> list[str]:
    lines: list[str] = []
    for node in nodes or []:
        kind = node.get("type")
        content = node.get("content")
        if kind == "paragraph":
            text = _inline(content).strip()
            if text:
                lines += [*text.split("\n"), ""]
        elif kind == "heading":
            level = int((node.get("attrs") or {}).get("level", 2))
            lines += ["#" * min(max(level, 1), 6) + " " + _inline(content).strip(), ""]
        elif kind in ("bulletList", "orderedList"):
            for i, item in enumerate(content or [], 1):
                marker = f"{i}. " if kind == "orderedList" else "- "
                inner = [line for line in _blocks(item.get("content")) if line]
                for j, line in enumerate(inner):  # nested lines indent under the marker
                    lines.append((marker if j == 0 else " " * len(marker)) + line)
            lines.append("")
        elif kind == "codeBlock":
            lang = (node.get("attrs") or {}).get("language") or ""
            lines += [f"```{lang}", *_inline(content).split("\n"), "```", ""]
        elif kind in ("blockquote", "panel"):
            inner = _blocks(content)
            while inner and not inner[-1]:
                inner.pop()
            lines += ["> " + line if line else ">" for line in inner]
            lines.append("")
        elif kind == "rule":
            lines += ["---", ""]
        elif kind == "table":
            rows = [
                [
                    _inline(_flatten(cell.get("content"))).strip().replace("|", "\\|")
                    for cell in row.get("content") or []
                ]
                for row in content or []
            ]
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                lines.append("| " + " | ".join(rows[0]) + " |")
                lines.append("|" + " --- |" * width)
                lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
                lines.append("")
        elif kind in ("mediaSingle", "mediaGroup", "media"):
            continue
        elif content:
            lines += _blocks(content)
    return lines


def _flatten(nodes):
    """Table cells hold paragraphs: flatten them into one inline run (paragraphs -> spaces)."""
    out = []
    for node in nodes or []:
        if node.get("type") == "paragraph":
            out += [*(node.get("content") or []), {"type": "text", "text": " "}]
        else:
            out.append(node)
    return out


def adf_to_markdown(doc: Mapping[str, Any] | str | None) -> str:
    if not doc:
        return ""
    if isinstance(doc, str):  # some fields come back as plain strings
        return doc.strip() + "\n"
    nodes = doc.get("content") if doc.get("type") == "doc" else [doc]  # a doc or a single node
    text = "\n".join(_blocks(nodes)).strip()
    return re.sub(r"\n{3,}", "\n\n", text) + ("\n" if text else "")


# --- wiki markup ---------------------------------------------------------------------------------

_CODE = re.compile(r"\{(code|noformat)(?::([^}]*))?\}(.*?)\{\1\}", re.S)
_PANEL = re.compile(r"\{(quote|panel|info|note|warning|tip)(?::[^}]*)?\}(.*?)\{\1\}", re.S)


def _wiki_inline(text: str) -> str:
    text = re.sub(r"\{\{(.+?)\}\}", r"`\1`", text)
    text = re.sub(r"\[([^|\]]+)\|([^\]]+)\]", r"[\1](\2)", text)
    text = re.sub(r"\[(https?://[^\]]+)\]", r"\1", text)
    text = re.sub(r"(?<![\w*])\*(\S(?:.*?\S)?)\*(?![\w*])", r"**\1**", text)
    text = re.sub(r"(?<![\w_])_(\S(?:.*?\S)?)_(?![\w_])", r"*\1*", text)
    text = re.sub(r"(?<![\w-])-(\S(?:.*?\S)?)-(?![\w-])", r"~~\1~~", text)
    text = re.sub(r"![^!\s]+!", "", text)  # images
    return text


def wiki_to_markdown(text: str | None) -> str:
    if not text:
        return ""
    blocks: list[str] = []

    def keep(match: re.Match) -> str:
        lang = (match.group(2) or "").split("|")[0] if match.group(1) == "code" else ""
        lang = "" if "=" in lang else lang
        blocks.append(f"```{lang}\n{match.group(3).strip(chr(10))}\n```")
        return f"\x00{len(blocks) - 1}\x00"

    text = _CODE.sub(keep, text.replace("\r\n", "\n"))
    text = _PANEL.sub(
        lambda m: "\n".join("> " + line for line in m.group(2).strip().split("\n")), text
    )
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        heading = re.match(r"h([1-6])\.\s+(.*)", stripped)
        bullet = re.match(r"([*#-]+)\s+(.*)", stripped)
        if heading:
            out.append("#" * int(heading.group(1)) + " " + _wiki_inline(heading.group(2)))
        elif stripped.startswith("||"):
            cells = [c.strip() for c in stripped.strip("|").split("||")]
            out += ["| " + " | ".join(map(_wiki_inline, cells)) + " |", "|" + " --- |" * len(cells)]
        elif stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            out.append("| " + " | ".join(map(_wiki_inline, cells)) + " |")
        elif bullet and not stripped.startswith("----"):
            marks = bullet.group(1)
            marker = "1. " if marks[-1] == "#" else "- "
            out.append("  " * (len(marks) - 1) + marker + _wiki_inline(bullet.group(2)))
        elif stripped == "----":
            out.append("---")
        else:
            out.append(_wiki_inline(line.rstrip()))
    result = "\n".join(out)
    result = re.sub(r"\x00(\d+)\x00", lambda m: blocks[int(m.group(1))], result)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result + ("\n" if result else "")
