"""Retention for persisted agent conversations (ADK's SQLite session store).

Conversations can contain answers built from confidential knowledge, so they are not kept
forever: sessions idle longer than SDLC_SESSION_RETENTION_DAYS (default 7) are deleted with their
events, at startup and then daily. Only `sqlite://` stores are handled here; other stores (Agent
Engine on GCP) have their own retention settings.
"""

import logging
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger("sdlc.web")

DAY_SECONDS = 86400


def sqlite_path(session_service_uri: str) -> Path | None:
    """File path of a sqlite:// session store (ADK strips one leading slash), else None."""
    parsed = urlparse(session_service_uri)
    if parsed.scheme != "sqlite" or not parsed.path:
        return None
    return Path(parsed.path[1:] if parsed.path.startswith("/") else parsed.path)


def purge_idle_sessions(db_path: Path, retention_days: float, now: float | None = None) -> int:
    """Delete sessions (and their events) not updated within the retention period."""
    if not db_path.exists():
        return 0
    cutoff = (time.time() if now is None else now) - retention_days * DAY_SECONDS
    with sqlite3.connect(db_path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "sessions" not in tables:
            return 0
        stale = conn.execute(
            "SELECT app_name, user_id, id FROM sessions WHERE update_time < ?", (cutoff,)
        ).fetchall()
        if "events" in tables:
            conn.executemany(
                "DELETE FROM events WHERE app_name=? AND user_id=? AND session_id=?", stale
            )
        conn.executemany("DELETE FROM sessions WHERE app_name=? AND user_id=? AND id=?", stale)
    return len(stale)


def start_retention(db_path: Path, retention_days: float, interval: float = DAY_SECONDS):
    """Purge now, then every `interval` seconds, in a daemon thread. Returns the stop event."""
    stop = threading.Event()

    def run() -> None:
        while True:
            try:
                removed = purge_idle_sessions(db_path, retention_days)
                if removed:
                    log.info("session retention: removed %d idle conversation(s)", removed)
            except sqlite3.Error:
                log.exception("session retention failed")
            if stop.wait(interval):
                return

    threading.Thread(target=run, name="session-retention", daemon=True).start()
    return stop
