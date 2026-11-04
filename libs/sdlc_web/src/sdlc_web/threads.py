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
"""

import logging
import re
from datetime import UTC, datetime

from ag_ui_adk.session_manager import APP_NAME_STATE_KEY, THREAD_ID_STATE_KEY
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from sdlc_web.middleware import current_oid

log = logging.getLogger("sdlc.web")

THREADS_PATH = "/threads"
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


def mount_threads(app: FastAPI, sessions, app_name: str) -> None:
    titles: dict[tuple[str, str], str] = {}

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
