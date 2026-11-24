"""The structural knowledge graph of one source, with no model calls (DEC-0011): the source contains its
files, a Markdown file its sections and a Python file its classes and functions; Markdown files link to files
and Python files import modules of the same source."""

import ast
import posixpath
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from sdlc_knowledge import Edge, Entity

from knowledge_ingest.chunking import MARKDOWN, headings

FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)
FRONT_TITLE = re.compile(r"^title:\s*[\"']?(.+?)[\"']?\s*$", re.M)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
CONTAINS, LINKS_TO, IMPORTS = "contains", "links_to", "imports"


@dataclass
class Graph:
    entities: list[Entity] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)


def source_entity_id(source_id: str) -> str:
    return f"{source_id}:source"


def file_entity_id(source_id: str, path: str) -> str:
    return f"{source_id}:file:{path}"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "x"


def _modules(paths: list[str]) -> dict[str, str]:
    """Dotted module name -> file, for every unambiguous suffix of each Python file's path
    (`libs/x/src/pkg/mod.py` answers `pkg.mod`, `src.pkg.mod`, ...)."""
    seen: dict[str, set[str]] = {}
    for path in paths:
        if not path.endswith(".py"):
            continue
        parts = path[:-3].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        for i in range(len(parts)):
            seen.setdefault(".".join(parts[i:]), set()).add(path)
    return {name: next(iter(files)) for name, files in seen.items() if len(files) == 1 and name}


def _python(sid: str, cls: str, path: str, text: str, h: str, modules: Mapping[str, str], g: Graph) -> None:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return
    file_id = file_entity_id(sid, path)

    def symbols(body, parent_id: str, prefix: str) -> None:
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{node.name}"
                sym_id = f"{sid}:symbol:{path}:{name}"
                doc = (ast.get_docstring(node) or "").split("\n\n")[0][:300]
                g.entities.append(Entity(sym_id, sid, cls, "symbol", name, path, doc, h))
                g.edges.append(Edge(sid, cls, parent_id, sym_id, CONTAINS, h))
                if isinstance(node, ast.ClassDef):
                    symbols(node.body, sym_id, f"{name}.")

    symbols(tree.body, file_id, "")
    package = path[:-3].split("/")[:-1] if not path.endswith("__init__.py") else path.split("/")[:-1]
    targets: set[str] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = ".".join([*package[: len(package) - node.level + 1], *([base] if base else [])])
            # `from pkg import mod` imports the module when there is one, else a name defined in the package.
            names = [f"{base}.{a.name}" if f"{base}.{a.name}" in modules else base for a in node.names] if base else []
        for name in names:
            target = modules.get(name)
            if target and target != path:
                targets.add(target)
    for target in sorted(targets):
        g.edges.append(Edge(sid, cls, file_id, file_entity_id(sid, target), IMPORTS, h))


def _markdown(sid: str, cls: str, path: str, text: str, h: str, paths: set[str], g: Graph) -> None:
    file_id = file_entity_id(sid, path)
    trail: list[tuple[int, str]] = []
    used: set[str] = set()
    for mark in headings(text):
        section_id = f"{sid}:section:{path}#{slug(mark.title)}"
        n = 2
        while section_id in used:
            section_id, n = f"{sid}:section:{path}#{slug(mark.title)}-{n}", n + 1
        used.add(section_id)
        trail = [(level, i) for level, i in trail if level < mark.level]
        g.entities.append(Entity(section_id, sid, cls, "section", mark.title, path, "", h))
        g.edges.append(Edge(sid, cls, trail[-1][1] if trail else file_id, section_id, CONTAINS, h))
        trail.append((mark.level, section_id))
    targets: set[str] = set()
    for match in LINK.finditer(text):
        target = match.group(1).split("#")[0]
        if not target or "://" in target or target.startswith(("mailto:", "/")):
            continue
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
        if resolved in paths and resolved != path:
            targets.add(resolved)
    for target in sorted(targets):
        g.edges.append(Edge(sid, cls, file_id, file_entity_id(sid, target), LINKS_TO, h))


def title(path: str, text: str) -> str:
    """A Markdown file's title: its front matter `title`, else its first heading."""
    if not path.lower().endswith(MARKDOWN):
        return ""
    front = FRONT_MATTER.match(text)
    match = FRONT_TITLE.search(front.group(1)) if front else None
    if match:
        return match.group(1).strip()
    marks = headings(text)
    return marks[0].title if marks else ""


def file_graph(
    sid: str, cls: str, path: str, text: str, file_hash: str, paths: set[str], modules: Mapping[str, str]
) -> Graph:
    """The entities and edges one file contributes, each stamped with its content hash."""
    g = Graph()
    g.entities.append(Entity(file_entity_id(sid, path), sid, cls, "file", path, path, title(path, text), file_hash))
    g.edges.append(Edge(sid, cls, source_entity_id(sid), file_entity_id(sid, path), CONTAINS, file_hash))
    if path.lower().endswith(MARKDOWN):
        _markdown(sid, cls, path, text, file_hash, paths, g)
    elif path.endswith(".py"):
        _python(sid, cls, path, text, file_hash, modules, g)
    return g


def modules_of(paths: list[str]) -> dict[str, str]:
    return _modules(paths)
