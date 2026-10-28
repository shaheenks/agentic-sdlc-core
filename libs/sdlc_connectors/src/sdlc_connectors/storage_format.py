"""Confluence storage format (XHTML with ac:/ri: elements) -> Markdown (version-01 M3).

Keeps what retrieval needs: headings (the Markdown chunker splits on them), paragraphs, lists,
tables, code blocks, links, and the text of panels (info/note/warning/...). Drops what has no text
value: macro parameters, images, emoticons, placeholders. Internal page links become their title.

Stdlib only (html.parser). Unknown elements keep their text, so nothing readable is lost.
"""

import re
from html.parser import HTMLParser

PANEL_MACROS = {"info", "note", "warning", "tip", "panel", "expand", "excerpt", "details"}
CODE_MACROS = {"code", "noformat"}
SKIPPED = {"ac:parameter", "ac:image", "ac:emoticon", "ac:placeholder", "ri:attachment", "style"}
BLOCKS = {"p", "div", "section", "dt", "dd", "ac:layout-cell", "ac:layout-section"}
BR = " "  # a <br> inside text; newlines in the source are only whitespace


class _Converter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.buf: list[str] = []
        self.lists: list[list] = []  # [kind, counter]
        self.li_marker: str | None = None
        self.quote = 0
        self.skip = 0
        self.heading = 0
        self.code: dict | None = None  # {"lang", "text": []}
        self.table: dict | None = None  # {"rows": [], "row": None, "cell": None}
        self.links: list[tuple[int, str | None]] = []
        self.macros: list[str] = []
        self.ac_link: dict | None = None
        self.param: str | None = None  # name of the ac:parameter being read

    # --- output ---------------------------------------------------------------------------------

    def _target(self) -> list[str]:
        if self.table is not None and self.table["cell"] is not None:
            return self.table["cell"]
        return self.buf

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self.buf)).replace(BR, "\n").strip()
        self.buf = []
        if not text:
            return
        if self.heading:
            text = "#" * self.heading + " " + text.replace("\n", " ")
        prefix = ""
        if self.lists:
            indent = "  " * (len(self.lists) - 1)
            if self.li_marker is not None:
                prefix, self.li_marker = indent + self.li_marker, None
            else:
                prefix = indent + "  "
        lines = [prefix + line.strip() for line in text.split("\n") if line.strip()]
        quote = "> " * self.quote
        self.out.extend(quote + line for line in lines)

    def _blank(self) -> None:
        if self.out and self.out[-1] != "":
            self.out.append("")

    def _block(self) -> None:
        if self.table is not None and self.table["cell"] is not None:
            self.table["cell"].append(" ")
        else:
            self._flush()

    # --- parser callbacks ---------------------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if self.code is not None and tag not in ("ac:plain-text-body",):
            if tag == "ac:parameter":
                self.param = a.get("ac:name")
            return
        if tag in SKIPPED:
            self.skip += 1
            if tag == "ac:parameter":
                self.param = a.get("ac:name")
            return
        if self.skip:
            return
        if tag == "ac:structured-macro":
            name = (a.get("ac:name") or "").lower()
            self.macros.append(name)
            if name in CODE_MACROS:
                self._block()
                self.code = {"lang": "", "text": []}
            elif name in PANEL_MACROS:
                self._flush()
                self._blank()
                self.quote += 1
            return
        if tag == "pre":
            self._block()
            self.code = {"lang": "", "text": [], "pre": True}
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush()
            self._blank()
            self.heading = int(tag[1])
        elif tag in BLOCKS:
            self._block()
        elif tag == "br":
            self._target().append(BR)
        elif tag == "hr":
            self._flush()
            self.out.extend(["", "---", ""])
        elif tag in ("strong", "b"):
            self._target().append("**")
        elif tag in ("em", "i"):
            self._target().append("*")
        elif tag in ("s", "del"):
            self._target().append("~~")
        elif tag == "code":
            self._target().append("`")
        elif tag == "a":
            self.links.append((len(self._target()), a.get("href")))
        elif tag in ("ul", "ol", "ac:task-list"):
            self._flush()
            self.lists.append([tag, 0])
        elif tag in ("li", "ac:task"):
            self._flush()
            if self.lists:
                kind = self.lists[-1]
                kind[1] += 1
                self.li_marker = f"{kind[1]}. " if kind[0] == "ol" else "- "
        elif tag == "ac:task-status":
            self.skip += 1
            self.param = "task-status"
        elif tag == "blockquote":
            self._flush()
            self.quote += 1
        elif tag == "table":
            self._flush()
            self._blank()
            self.table = {"rows": [], "row": None, "cell": None}
        elif tag == "tr" and self.table is not None:
            self.table["row"] = []
        elif tag in ("td", "th") and self.table is not None:
            self.table["cell"] = []
        elif tag == "ac:link":
            self.ac_link = {"title": None, "text": []}
        elif tag in ("ri:page", "ri:blog-post") and self.ac_link is not None:
            self.ac_link["title"] = a.get("ri:content-title")
        elif tag == "time" and a.get("datetime"):
            self._target().append(a["datetime"])

    def handle_endtag(self, tag: str) -> None:
        if self.code is not None:
            if tag == "ac:parameter":
                self.param = None
                return
            if (tag == "pre" and self.code.get("pre")) or (
                tag == "ac:structured-macro" and self.macros and self.macros[-1] in CODE_MACROS
            ):
                if tag == "ac:structured-macro":
                    self.macros.pop()
                self._emit_code()
            return
        if tag in SKIPPED or (tag == "ac:task-status" and self.skip):
            self.skip = max(0, self.skip - 1)
            self.param = None
            return
        if self.skip:
            return
        if tag == "ac:structured-macro":
            name = self.macros.pop() if self.macros else ""
            if name in PANEL_MACROS:
                self._flush()
                self.quote = max(0, self.quote - 1)
                self._blank()
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush()
            self.heading = 0
            self._blank()
        elif tag in BLOCKS:
            if self.table is not None and self.table["cell"] is not None:
                self.table["cell"].append(" ")
            else:
                self._flush()
                if not self.lists:
                    self._blank()
        elif tag in ("strong", "b"):
            self._target().append("**")
        elif tag in ("em", "i"):
            self._target().append("*")
        elif tag in ("s", "del"):
            self._target().append("~~")
        elif tag == "code":
            self._target().append("`")
        elif tag == "a" and self.links:
            start, href = self.links.pop()
            target = self._target()
            text = "".join(target[start:]).strip()
            del target[start:]
            if href and text and text != href and not href.startswith("#"):
                target.append(f"[{text}]({href})")
            else:
                target.append(text or href or "")
        elif tag in ("ul", "ol", "ac:task-list"):
            self._flush()
            if self.lists:
                self.lists.pop()
            if not self.lists:
                self._blank()
        elif tag in ("li", "ac:task"):
            self._flush()
        elif tag == "blockquote":
            self._flush()
            self.quote = max(0, self.quote - 1)
            self._blank()
        elif tag in ("td", "th") and self.table is not None and self.table["cell"] is not None:
            text = re.sub(r"\s+", " ", "".join(self.table["cell"]).replace(BR, " "))
            text = text.strip().replace("|", "\\|")
            if self.table["row"] is not None:
                self.table["row"].append(text)
            self.table["cell"] = None
        elif tag == "tr" and self.table is not None and self.table["row"] is not None:
            self.table["rows"].append(self.table["row"])
            self.table["row"] = None
        elif tag == "table" and self.table is not None:
            self._emit_table()
        elif tag == "ac:link" and self.ac_link is not None:
            text = re.sub(r"\s+", " ", "".join(self.ac_link["text"])).strip()
            self.ac_link, value = None, text or self.ac_link["title"] or ""
            self._target().append(value)

    def handle_startendtag(self, tag, attrs) -> None:
        if tag in SKIPPED:
            return  # self-closing: nothing to skip
        self.handle_starttag(tag, attrs)
        if tag not in ("br", "hr"):
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.code is not None:
            if self.param == "language":
                self.code["lang"] = data.strip()
            elif self.param is None:
                self.code["text"].append(data)
            return
        if self.skip:
            if self.param == "task-status" and data.strip() == "complete" and self.li_marker:
                self.li_marker = self.li_marker + "[x] "
            return
        if self.ac_link is not None:
            self.ac_link["text"].append(data)
            return
        self._target().append(data)

    def unknown_decl(self, data: str) -> None:
        if data.startswith("CDATA["):
            self.handle_data(data[len("CDATA[") :])

    # --- blocks ---------------------------------------------------------------------------------

    def _emit_code(self) -> None:
        code, self.code = self.code, None
        body = "".join(code["text"]).strip("\n")
        if not body.strip():
            return
        self._flush()
        self._blank()
        quote = "> " * self.quote
        self.out.append(quote + "```" + code["lang"])
        self.out.extend(quote + line for line in body.split("\n"))
        self.out.append(quote + "```")
        self._blank()

    def _emit_table(self) -> None:
        table, self.table = self.table, None
        rows = [r for r in table["rows"] if any(c for c in r)]
        if not rows:
            return
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        self.out.append("| " + " | ".join(rows[0]) + " |")
        self.out.append("|" + " --- |" * width)
        self.out.extend("| " + " | ".join(r) + " |" for r in rows[1:])
        self._blank()

    def markdown(self) -> str:
        self._flush()
        text = "\n".join(self.out).strip()
        return re.sub(r"\n{3,}", "\n\n", text) + ("\n" if text else "")


def storage_to_markdown(xhtml: str) -> str:
    converter = _Converter()
    converter.feed(xhtml or "")
    converter.close()
    return converter.markdown()
