"""GET /threads: the caller's previous conversations, for the chat app's history (version-02 N15).

Read-only and per user: it lists the ADK sessions of the validated caller (`current_oid()`, set by
EntraUserBindingMiddleware) in the same session store the AG-UI endpoint writes, so the list holds
exactly what /agents/state can open for that user. Each entry is
`{threadId, title, updatedAt}`:
- `threadId`: the AG-UI thread a session belongs to (ag_ui_adk's thread key in session state), or
  the session id for sessions started in the ADK dev UI (ag_ui_adk opens those by id);
- `title`: the first user message, whitespace collapsed and cut to TITLE_CHARS. Nothing else from
  the session (state, tool calls, results, tokens) is returned. Sessions without a user message
  are left out.
Titles never change once set, so they are cached per (user, session) in this process; listing
costs one list_sessions call plus one read per session not seen before.

DELETE /threads/{threadId} deletes one of the caller's conversations (hard delete, session and
events, from the session store). The thread is resolved exactly as /agents/state resolves it
(ag_ui_adk's lookup, scoped to the caller), so a thread that does not exist and one that belongs
to someone else both answer 404. The request must carry `X-SDLC-Request: 1`: a cross-site page
cannot send a custom header without a CORS preflight, which the agent never grants. ag_ui_adk's
in-process thread -> session mapping and the title cache are cleared; the delete is logged
(oid and thread id, no content).
"""

import logging
import re
from datetime import UTC, datetime

from ag_ui_adk.session_manager import APP_NAME_STATE_KEY, THREAD_ID_STATE_KEY
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from sdlc_web.middleware import current_oid

log = logging.getLogger("sdlc.web")

THREADS_PATH = "/threads"
REQUEST_HEADER = "x-sdlc-request"  # required on DELETE (see module docstring)
THREAD_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
MAX_THREADS = 30  # newest first
MAX_SCAN = 60  # sessions examined per listing (some have no user message yet)
TITLE_CHARS = 60
_CACHE_LIMIT = 5000
_SPACE = re.compile(r"\s+")


def title_of(text: str) -> str:
    text = _SPACE.sub(" ", text).strip()
    return text if len(text) <= TITLE_CHARS else text[: TITLE_CHARS - 1].rstrip() + "…"


def first_user_text(events) -> str:
    for event in events or ():
        if getattr(event, "author", None) != "user" or not getattr(event, "content", None):
            continue
        text = " ".join(p.text for p in event.content.parts or () if getattr(p, "text", None))
        if text.strip():
            return text
    return ""


def _updated(session) -> str:
    seconds = getattr(session, "last_update_time", None) or 0
    return datetime.fromtimestamp(seconds, tz=UTC).isoformat(timespec="seconds")


def mount_threads(app: FastAPI, sessions, app_name: str, agent=None) -> None:
    """`agent`: the ag_ui_adk ADKAgent serving /agui (its session lookup resolves and its
    caches are cleared on delete); without it, DELETE resolves by session id only."""
    titles: dict[tuple[str, str], str] = {}

    async def resolve(oid: str, thread_id: str):
        if agent is not None:
            return await agent._session_manager.resolve_existing_session(
                thread_id=thread_id, app_name=app_name, user_id=oid
            )
        return await sessions.get_session(app_name=app_name, user_id=oid, session_id=thread_id)

    def forget(oid: str, thread_id: str, session_id: str) -> None:
        titles.pop((oid, session_id), None)
        if agent is not None:  # ag_ui_adk keeps these per process; a stale entry would point
            agent._session_lookup_cache.pop((thread_id, oid, app_name), None)  # at nothing
            agent._session_manager.invalidate_session(session_id, app_name, oid)

    @app.delete(THREADS_PATH + "/{thread_id}", include_in_schema=False)
    async def delete_thread(thread_id: str, request: Request):
        if request.headers.get(REQUEST_HEADER) != "1":
            return JSONResponse({"detail": "missing request header"}, status_code=403)
        not_found = JSONResponse({"detail": "no such conversation"}, status_code=404)
        if not THREAD_ID.fullmatch(thread_id):
            return not_found
        oid = current_oid()
        try:
            session = await resolve(oid, thread_id)
            owner_app = (session.state or {}).get(APP_NAME_STATE_KEY, app_name) if session else None
            if owner_app != app_name:
                return not_found  # missing, another user's, or another app's: all look the same
            await sessions.delete_session(app_name=app_name, user_id=oid, session_id=session.id)
        except Exception as e:
            log.warning("conversation delete failed: %s", type(e).__name__)
            return JSONResponse({"detail": "history unavailable"}, status_code=503)
        forget(oid, thread_id, session.id)
        log.info("conversation deleted: oid=%s thread=%s", oid, thread_id)
        return Response(status_code=204)

    async def title_for(oid: str, session) -> str:
        key = (oid, session.id)
        if key in titles:
            return titles[key]
        full = await sessions.get_session(app_name=app_name, user_id=oid, session_id=session.id)
        title = title_of(first_user_text(full.events if full else ()))
        if title:  # an empty session may still get its first message: look again next time
            if len(titles) >= _CACHE_LIMIT:
                titles.clear()
            titles[key] = title
        return title

    @app.get(THREADS_PATH, include_in_schema=False)
    async def list_threads():
        oid = current_oid()
        try:
            listed = (await sessions.list_sessions(app_name=app_name, user_id=oid)).sessions
            listed = sorted(listed, key=lambda s: s.last_update_time or 0, reverse=True)
            threads = []
            for session in listed[:MAX_SCAN]:
                state = session.state or {}
                if state.get(APP_NAME_STATE_KEY, app_name) != app_name:
                    continue  # another app sharing the store (Agent Engine)
                title = await title_for(oid, session)
                if not title:
                    continue
                threads.append(
                    {
                        "threadId": state.get(THREAD_ID_STATE_KEY) or session.id,
                        "title": title,
                        "updatedAt": _updated(session),
                    }
                )
                if len(threads) >= MAX_THREADS:
                    break
        except Exception as e:  # never leak store details to the browser
            log.warning("thread listing failed: %s", type(e).__name__)
            return JSONResponse({"detail": "history unavailable"}, status_code=503)
        return JSONResponse({"threads": threads}, headers={"cache-control": "no-store"})
