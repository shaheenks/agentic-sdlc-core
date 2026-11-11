"""A2UI cards from MCP tool results (version-03 P4, C1).

The agent shows citations, the caller's identity and connected-tool results as A2UI v0.9 surfaces
from the standard (basic) catalog. Rules (version-03 decisions U1-U4):
- Cards are built **deterministically from the tool result** with the A2UI SDK's builder. The
  model never writes UI.
- Links are `http(s)` only and open with the catalog's `openUrl`. A2UI user actions are input to
  the agent, never authorization.
- Every surface is validated strictly against the basic catalog before it is sent. Anything
  invalid, empty or unexpected gives **no card**: the chat still shows the answer.
- Cards are compact: citations are one caption plus a row of document chips that open their
  link; identity is one line with the details in a dialog.
- The cards travel under `a2ui_operations` in the tool result, for A2A clients (version-03 P4
  C3). The chat (/chat/) ignores them and keeps its own compact renderers (C2 decision).
  `after_tool_callback` removes any `a2ui_operations` a tool result already carries, so only
  cards built here are rendered.
  `before_model_callback` removes them from the model's copy of the conversation, so the model
  neither pays for them nor sees them.

Text from tool results (titles, paths, provider content) is untrusted. It is shown as plain text
(control characters removed, length capped), never as a link or markup.
"""

import json
import logging
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from a2ui.builder.v0_9 import (
    Action,
    Button,
    Card,
    Column,
    ComponentBuilderNode,
    ComponentTree,
    Modal,
    OpenUrl,
    Row,
    Text,
)
from a2ui.core.basic_catalog import BasicCatalog
from a2ui.core.processing.message_processor import MessageProcessor, MessageProcessorOptions
from a2ui.core.validation.payload_validator import STRICT_VALIDATION

log = logging.getLogger("sdlc.agent")

A2UI_KEY = "a2ui_operations"  # read by @ag-ui/a2ui-middleware in TOOL_CALL_RESULT content
VERSION = "v0.9"
MAX_DOCS = 10
MAX_TEXT = 200
MAX_URL = 2048
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩]")
_SURFACE_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")

Payload = dict[str, Any]


# --- reading tool results ------------------------------------------------------------------------


def tool_payload(response: Any) -> Payload | None:
    """The structured result of a tool call: an MCP result's `structuredContent` (unwrapped from
    `{"result": ...}`), else its first text item parsed as JSON, else the dict itself."""
    if not isinstance(response, dict):
        return None
    structured = response.get("structuredContent")
    if isinstance(structured, dict):
        inner = structured.get("result")
        return inner if set(structured) == {"result"} and isinstance(inner, dict) else structured
    content = response.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                try:
                    parsed = json.loads(item["text"])
                except ValueError:
                    return None
                return parsed if isinstance(parsed, dict) else None
        return None
    return response


def safe_url(value: Any) -> str | None:
    """`http(s)` URLs with a host only; anything else is not linked."""
    if not isinstance(value, str) or len(value) > MAX_URL or _CONTROL.search(value) or " " in value:
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None
    return value


def plain(value: Any, limit: int = MAX_TEXT) -> str:
    """Untrusted text for display: control and direction characters removed, length capped."""
    text = " ".join(_CONTROL.sub(" ", str(value)).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --- cards ---------------------------------------------------------------------------------------


def _open_button(url: str | None, label: str = "Open") -> list[ComponentBuilderNode]:
    link = safe_url(url)
    if not link:
        return []
    return [
        Button(
            child=Text(text=label),
            variant="borderless",
            action=Action(function_call=OpenUrl(url=link)),
        )
    ]


def _count(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def citations(payload: Payload, label: str) -> ComponentBuilderNode | None:
    """search_knowledge / graph_query: one compact line, "<label> · N docs", then one chip per
    document (title or file name, ×hits) that opens its link; documents without a link are plain
    text. Snippets stay out: the answer quotes what matters."""
    results = payload.get("results")
    if not isinstance(results, list):
        return None
    docs: dict[tuple[str, str], Payload] = {}
    for hit in results:
        if not isinstance(hit, dict) or not hit.get("path"):
            continue
        key = (str(hit.get("source", "")), str(hit["path"]))
        doc = docs.setdefault(key, {"hit": hit, "hits": 0, "url": None, "graph": False})
        doc["hits"] += 1
        doc["url"] = doc["url"] or safe_url(hit.get("url"))
        doc["graph"] = doc["graph"] or hit.get("via") == "graph"
    if not docs:
        return None
    chips: list[ComponentBuilderNode] = []
    for doc in list(docs.values())[:MAX_DOCS]:
        hit = doc["hit"]
        name = plain(hit.get("title") or str(hit["path"]).rsplit("/", 1)[-1], 60)
        if doc["hits"] > 1:
            name += f" ×{doc['hits']}"
        if doc["url"]:
            chips += _open_button(doc["url"], name)
        else:
            chips.append(Text(text=name, variant="caption"))
    if len(docs) > MAX_DOCS:
        chips.append(Text(text=f"+{len(docs) - MAX_DOCS}", variant="caption"))
    header = f"{plain(label)} · {_count(len(docs), 'doc')}"
    if any(d["graph"] for d in docs.values()):
        header += " · via knowledge graph"
    return Column(children=[Text(text=header, variant="caption"), Row(children=chips)])


def identity(payload: Payload) -> ComponentBuilderNode | None:
    """whoami: one line ("Signed in as Paul · 1 team · 1 role"); the details open in a dialog."""
    if not isinstance(payload.get("oid"), str):
        return None
    policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}

    def items(value: Any) -> list[str]:
        return [plain(x, 60) for x in (list(value) if isinstance(value, dict | list) else [])][:20]

    teams = items(policy.get("teams"))
    roles = [r for r in items(policy.get("roles")) if r != "signed-in"]
    app_roles = items(payload.get("app_roles"))
    who = plain(payload.get("name") or payload.get("upn") or "you", 80)
    facts = [_count(len(teams), "team")] if teams else []
    facts += [_count(len(roles), "role")] if roles else []
    rows: list[ComponentBuilderNode] = [Text(text=who, variant="h4")]
    if payload.get("upn"):
        rows.append(Text(text=plain(payload["upn"]), variant="caption"))
    if policy:
        rows.append(Text(text=f"Teams: {', '.join(teams) or 'none'}"))
        rows.append(Text(text=f"Roles: {', '.join(roles) or 'none'}"))
    rows.append(Text(text=f"App roles: {', '.join(app_roles) or 'none'}"))
    return Row(
        align="center",
        children=[
            Text(text=" · ".join([f"Signed in as {who}", *facts])),
            Modal(trigger=Text(text="Details", variant="caption"), content=Column(children=rows)),
        ],
    )


def connected(label: str) -> Callable[[Payload], ComponentBuilderNode | None]:
    """github_get_file & co.: what was read with the user's own account, or why not."""

    def build(payload: Payload) -> ComponentBuilderNode | None:
        if payload.get("connected") is False:
            reason = plain(payload.get("reason") or "no usable connection", 300)
            rows: list[ComponentBuilderNode] = [
                Text(text=f"{label}: account not connected", variant="h4"),
                Text(text=f"{reason}. Connect it on the Connections page."),
            ]
            return Card(child=Column(children=rows))
        title = payload.get("title") or payload.get("summary") or payload.get("path")
        title = title or payload.get("key")
        if not title:
            return None
        meta = f"with your {plain(payload.get('connection', ''), 40)} account"
        if payload.get("truncated") is True:
            meta += " · truncated"
        rows = [
            Text(text=f"{label}: {plain(title)}", variant="h4"),
            Text(text=meta, variant="caption"),
        ]
        if payload.get("connection_warning"):
            rows.append(Text(text=plain(payload["connection_warning"], 300)))
        rows += _open_button(payload.get("url"))
        return Card(child=Column(children=rows))

    return build


BUILDERS: dict[str, Callable[[Payload], ComponentBuilderNode | None]] = {
    "search_knowledge": lambda p: citations(p, "Sources"),
    "graph_query": lambda p: citations(p, "Sources (knowledge graph)"),
    "whoami": identity,
    "github_get_file": connected("GitHub file"),
    "bitbucket_get_file": connected("Bitbucket file"),
    "jira_get_issue": connected("Jira issue"),
    "confluence_get_page": connected("Confluence page"),
}


# --- surfaces ------------------------------------------------------------------------------------

_CATALOG = BasicCatalog(VERSION)
_STRICT = MessageProcessorOptions(validation_config=STRICT_VALIDATION)


def surface_id(tool_name: str, call_id: str | None) -> str:
    return _SURFACE_UNSAFE.sub("-", f"{tool_name}-{call_id or 'call'}")[:120]


def build_operations(tool_name: str, response: Any, surface: str) -> list[dict] | None:
    """A2UI v0.9 messages (createSurface + updateComponents) for one tool result, or None."""
    builder = BUILDERS.get(tool_name)
    if builder is None or (isinstance(response, dict) and response.get("isError") is True):
        return None
    payload = tool_payload(response)
    if payload is None:
        return None
    try:
        root = builder(payload)
        if root is None:
            return None
        components = ComponentTree(root, surface_id=surface).flatten()
        messages = [
            {
                "version": VERSION,
                "createSurface": {"surfaceId": surface, "catalogId": _CATALOG.catalog_id},
            },
            {
                "version": VERSION,
                "updateComponents": {"surfaceId": surface, "components": components},
            },
        ]
        MessageProcessor([_CATALOG], options=_STRICT).process_messages(messages)
    except Exception as e:  # a card is never worth failing the answer for
        log.warning("no A2UI card for %s: %s", tool_name, type(e).__name__)
        return None
    return messages


def without_cards(response: Any) -> Any:
    """The tool result without any `a2ui_operations` (a copy when there were some)."""
    if isinstance(response, dict) and A2UI_KEY in response:
        return {k: v for k, v in response.items() if k != A2UI_KEY}
    return response


# --- ADK callbacks -------------------------------------------------------------------------------


def after_tool_callback(tool, args, tool_context, tool_response):  # noqa: ARG001 (ADK signature)
    """Attach cards built from the result; drop any the tool itself returned."""
    clean = without_cards(tool_response)
    surface = surface_id(tool.name, getattr(tool_context, "function_call_id", None))
    operations = build_operations(tool.name, clean, surface)
    if operations:
        return {**clean, A2UI_KEY: operations}
    return clean if clean is not tool_response else None


def before_model_callback(callback_context, llm_request):  # noqa: ARG001 (ADK signature)
    """Remove cards from the model's copy of the conversation (the session keeps them)."""
    for content in llm_request.contents or []:
        for i, part in enumerate(content.parts or []):
            fr = part.function_response
            if fr is not None and isinstance(fr.response, dict) and A2UI_KEY in fr.response:
                # copies, so the session's own event keeps its cards
                trimmed = fr.model_copy(update={"response": without_cards(fr.response)})
                content.parts[i] = part.model_copy(update={"function_response": trimmed})
    return None
