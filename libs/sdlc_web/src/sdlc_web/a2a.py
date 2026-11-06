"""A2A endpoint (version-03 P4 C3): the same agent for A2A clients such as Gemini Enterprise.

JSON-RPC (A2A 0.3, a2a-sdk) at `/a2a`, agent card at `/.well-known/agent-card.json`, on the same
app as /agui and behind the same EntraUserBindingMiddleware (decision U5):
- The user is the validated token's `oid` (the middleware's `current_oid`), put into the A2A call
  context. ADK's fallback user `A2A_USER_<context_id>` is never used: no verified user = refused.
  The call context carries no request headers, so the token never reaches A2A or session state;
  it stays in the request ContextVar, which the agent run inherits (MCP calls carry the user).
- One A2A context = one conversation in the configured session store (sessions are keyed by
  (app, user, id), so the same context id from another user can only reach that user's own
  session). On top of that, a context or task started by another user is refused ("unknown
  context" / task not found): tasks are kept per owner (`OwnerTaskStore`).
- Input: text parts only. Data and file parts (including forged function calls or results) and
  client metadata are dropped; clients cannot set session state. No push notifications (the
  server never calls client-supplied URLs).
- Output: the agent's events as A2A messages. A2UI cards built from tool results
  (`sdlc_agent.a2ui_cards`) leave as separate DataParts with `mimeType: application/json+a2ui`;
  the function-result DataPart is sent without them.
- Errors: details are logged; the client gets a generic failure message.
Tasks live in memory (lost on restart, per instance); the conversation itself is in the
session store.
"""

import logging
import re
from collections import OrderedDict
from typing import Any

from a2a.auth.user import User
from a2a.extensions.common import HTTP_EXTENSION_HEADER, get_requested_extensions
from a2a.server.apps.jsonrpc.jsonrpc_app import CallContextBuilder
from a2a.server.apps.jsonrpc.starlette_app import A2AStarletteApplication
from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentSkill,
    HTTPAuthSecurityScheme,
    InvalidParamsError,
    SecurityScheme,
    Task,
    TextPart,
)
from a2a.utils.errors import ServerError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.adk.a2a import _compat
from google.adk.a2a.converters.part_converter import (
    convert_a2a_part_to_genai_part,
    convert_genai_part_to_a2a_part,
)
from google.adk.a2a.converters.request_converter import (
    AgentRunRequest,
    convert_a2a_request_to_agent_run_request,
)
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.a2a.executor.config import A2aAgentExecutorConfig
from google.adk.agents import BaseAgent
from google.adk.agents.run_config import RunConfig
from google.adk.artifacts import InMemoryArtifactService
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai import types as genai_types
from sdlc_agent.a2ui_cards import A2UI_KEY, without_cards

log = logging.getLogger("sdlc.web")

A2A_PATH = "/a2a"
CARD_PATH = "/.well-known/agent-card.json"
A2UI_MIME = "application/json+a2ui"
# A2UI's A2A extension; clients that support it render the DataParts above (re-checked in C5)
A2UI_EXTENSION = "https://a2ui.org/a2a-extension/a2ui/v0.9"
GENERIC_FAILURE = "The agent could not complete this request."
# context ids become session ids: the Agent Engine session id alphabet, bounded
_CONTEXT_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
MAX_TASKS = 5000


# --- identity -----------------------------------------------------------------------------------


class EntraUser(User):
    def __init__(self, oid: str):
        self._oid = oid

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def user_name(self) -> str:
        return self._oid


def _oid(context: ServerCallContext | None) -> str | None:
    if context is None or not context.user.is_authenticated:
        return None
    return context.user.user_name or None


class EntraCallContextBuilder(CallContextBuilder):
    """The caller is the oid the middleware verified; no headers (and so no token) in state."""

    def build(self, request: Request) -> ServerCallContext:
        from sdlc_web.middleware import current_oid

        return ServerCallContext(
            user=EntraUser(current_oid()),  # raises outside a verified request: fail closed
            requested_extensions=get_requested_extensions(
                request.headers.getlist(HTTP_EXTENSION_HEADER)
            ),
        )


# --- tasks per owner -----------------------------------------------------------------------------


class OwnerTaskStore(TaskStore):
    """Tasks visible only to the user who started them; contexts remembered per owner."""

    def __init__(self, limit: int = MAX_TASKS):
        self._tasks = InMemoryTaskStore()
        self._owners: OrderedDict[str, str] = OrderedDict()  # task id -> oid
        self._contexts: OrderedDict[str, str] = OrderedDict()  # context id -> oid
        self._limit = limit

    def context_owner(self, context_id: str) -> str | None:
        return self._contexts.get(context_id)

    async def save(self, task: Task, context: ServerCallContext | None = None) -> None:
        oid = _oid(context)
        if oid is None or self._owners.get(task.id, oid) != oid:
            raise PermissionError("task belongs to another user")
        if self._contexts.get(task.context_id, oid) != oid:
            raise PermissionError("context belongs to another user")
        await self._tasks.save(task, context)
        self._owners[task.id] = oid
        self._owners.move_to_end(task.id)
        self._contexts[task.context_id] = oid
        self._contexts.move_to_end(task.context_id)
        while len(self._owners) > self._limit:
            old, _ = self._owners.popitem(last=False)
            await self._tasks.delete(old)
        while len(self._contexts) > self._limit:
            self._contexts.popitem(last=False)

    async def get(self, task_id: str, context: ServerCallContext | None = None) -> Task | None:
        oid = _oid(context)
        if oid is None or self._owners.get(task_id) != oid:
            return None  # another user's task is "not found"
        return await self._tasks.get(task_id, context)

    async def delete(self, task_id: str, context: ServerCallContext | None = None) -> None:
        oid = _oid(context)
        if oid is not None and self._owners.get(task_id) == oid:
            await self._tasks.delete(task_id, context)
            self._owners.pop(task_id, None)


class OwnerRequestHandler(DefaultRequestHandler):
    """Refuses a message that names another user's context, or a malformed context id."""

    def __init__(self, *, task_store: OwnerTaskStore, **kwargs: Any):
        super().__init__(task_store=task_store, **kwargs)
        self._owner_store = task_store

    def _check_context(self, params: Any, context: ServerCallContext | None) -> None:
        oid = _oid(context)
        if oid is None:
            raise ServerError(error=InvalidParamsError(message="sign-in required"))
        context_id = params.message.context_id
        if context_id is None:
            return  # a new conversation: the server picks the id
        owner = self._owner_store.context_owner(context_id)
        if not _CONTEXT_ID.fullmatch(context_id) or (owner is not None and owner != oid):
            raise ServerError(error=InvalidParamsError(message="unknown context"))

    async def on_message_send(self, params, context=None):
        self._check_context(params, context)
        return await super().on_message_send(params, context)

    async def on_message_send_stream(self, params, context=None):
        self._check_context(params, context)
        async for event in super().on_message_send_stream(params, context):
            yield event


# --- conversion ----------------------------------------------------------------------------------


def to_run_request(request, part_converter=convert_a2a_part_to_genai_part) -> AgentRunRequest:
    """ADK's conversion, with the verified user, no client state and no client metadata."""
    oid = _oid(request.call_context)
    if oid is None:
        raise PermissionError("no verified user for this A2A request")
    run = convert_a2a_request_to_agent_run_request(request, part_converter)
    if not run.new_message or not run.new_message.parts:
        raise ValueError("send at least one text part")
    return run.model_copy(update={"user_id": oid, "state_delta": None, "run_config": RunConfig()})


def text_parts_only(part) -> genai_types.Part | None:
    """Client input: text only. Data/file parts (e.g. forged function results) are dropped."""
    if isinstance(getattr(part, "root", part), TextPart):
        converted = convert_a2a_part_to_genai_part(part)
        if isinstance(converted, genai_types.Part) and converted.text is not None:
            return genai_types.Part(text=converted.text)  # no client part metadata
    return None


def with_a2ui_parts(part: genai_types.Part):
    """Agent output: A2UI cards travel as their own DataParts (`application/json+a2ui`)."""
    response = part.function_response
    if response is None or not isinstance(response.response, dict):
        return convert_genai_part_to_a2a_part(part)
    operations = response.response.get(A2UI_KEY)
    if not operations:
        return convert_genai_part_to_a2a_part(part)
    trimmed = response.model_copy(update={"response": without_cards(response.response)})
    base = convert_genai_part_to_a2a_part(part.model_copy(update={"function_response": trimmed}))
    parts = [base] if base is not None else []
    parts += [
        _compat.make_data_part(data=op, metadata={"mimeType": A2UI_MIME})
        for op in operations
        if isinstance(op, dict)
    ]
    return parts


class SdlcA2aExecutor(A2aAgentExecutor):
    """ADK's executor; failures are logged here and reported to the client without details."""

    async def _handle_request(self, context, event_queue):
        try:
            await super()._handle_request(context, event_queue)
        except Exception:
            log.exception("A2A request failed (task %s)", context.task_id)
            raise RuntimeError(GENERIC_FAILURE) from None


# --- card and routes -----------------------------------------------------------------------------


def agent_card(url: str, agent: BaseAgent) -> AgentCard:
    return AgentCard(
        name=agent.name,
        description=agent.description or "SDLC assistant",
        url=url,
        version="1.0.0",
        protocol_version="0.3.0",
        preferred_transport="JSONRPC",
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=False,
            state_transition_history=False,
            extensions=[
                AgentExtension(
                    uri=A2UI_EXTENSION,
                    description="A2UI v0.9 cards (basic catalog) as application/json+a2ui parts",
                    required=False,
                )
            ],
        ),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain", "application/json", A2UI_MIME],
        skills=[
            AgentSkill(
                id="sdlc-assistant",
                name="SDLC assistant",
                description=(
                    "Answers questions about your team's code, runbooks, standards and incidents "
                    "with the knowledge and tools you are allowed to use."
                ),
                tags=["sdlc", "knowledge"],
            )
        ],
        security_schemes={
            "entra": SecurityScheme(
                root=HTTPAuthSecurityScheme(
                    scheme="bearer",
                    bearer_format="JWT",
                    description="Entra ID access token for the SDLC API (scope access_as_user)",
                )
            )
        },
        security=[{"entra": []}],
    )


def mount_a2a(
    app: FastAPI,
    agent: BaseAgent,
    agent_name: str,
    sessions: BaseSessionService,
    public_url: str | None = None,
) -> OwnerTaskStore:
    """Add the A2A routes. `public_url` is the advertised /a2a URL (SDLC_A2A_URL); without it the
    card names the URL the request came in on."""
    runner = Runner(
        app_name=agent_name,  # same app as adk web and /agui: one store layout
        agent=agent,
        session_service=sessions,
        artifact_service=InMemoryArtifactService(),
    )
    executor = SdlcA2aExecutor(
        runner=runner,
        config=A2aAgentExecutorConfig(
            request_converter=to_run_request,
            a2a_part_converter=text_parts_only,
            gen_ai_part_converter=with_a2ui_parts,
        ),
        use_legacy=True,  # one tested conversion path, whatever extensions a client asks for
    )
    store = OwnerTaskStore()
    handler = OwnerRequestHandler(agent_executor=executor, task_store=store)
    base_card = agent_card(public_url or "http://placeholder" + A2A_PATH, agent)
    a2a_app = A2AStarletteApplication(
        agent_card=base_card, http_handler=handler, context_builder=EntraCallContextBuilder()
    )
    rpc = [r for r in a2a_app.routes(rpc_url=A2A_PATH) if r.name == "a2a_handler"]
    app.router.routes.extend(rpc)

    @app.get(CARD_PATH, include_in_schema=False)
    async def card(request: Request) -> JSONResponse:
        url = public_url or str(request.base_url).rstrip("/") + A2A_PATH
        body = base_card.model_copy(update={"url": url})
        return JSONResponse(
            body.model_dump(mode="json", by_alias=True, exclude_none=True),
            headers={"cache-control": "no-store"},
        )

    return store
