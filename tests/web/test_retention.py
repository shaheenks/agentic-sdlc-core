"""H9: persisted conversations are purged after the retention period."""

import sqlite3
import time
from pathlib import Path

from sdlc_web.retention import DAY_SECONDS, purge_idle_sessions, sqlite_path


def make_store(path: Path, sessions: dict[str, float]) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE sessions (app_name TEXT, user_id TEXT, id TEXT, state TEXT,"
            " create_time REAL, update_time REAL, PRIMARY KEY (app_name, user_id, id))"
        )
        conn.execute(
            "CREATE TABLE events (id TEXT, app_name TEXT, user_id TEXT, session_id TEXT,"
            " invocation_id TEXT, timestamp REAL, event_data TEXT)"
        )
        for sid, updated in sessions.items():
            conn.execute(
                "INSERT INTO sessions VALUES ('bootstrap', 'u1', ?, '{}', ?, ?)",
                (sid, updated, updated),
            )
            conn.execute(
                "INSERT INTO events VALUES (?, 'bootstrap', 'u1', ?, 'i', ?, '{}')",
                (f"e-{sid}", sid, updated),
            )


def test_sqlite_path_follows_adk_uri_rules():
    assert sqlite_path("sqlite:////data/sessions.db") == Path("/data/sessions.db")
    assert sqlite_path("sqlite:///rel/sessions.db") == Path("rel/sessions.db")
    assert sqlite_path("memory://") is None
    assert sqlite_path("sqlite://") is None  # ADK treats this as in-memory
    assert sqlite_path("agentengine://123") is None


def test_idle_sessions_and_their_events_are_purged(tmp_path):
    now = time.time()
    db = tmp_path / "sessions.db"
    make_store(db, {"old": now - 8 * DAY_SECONDS, "recent": now - 2 * DAY_SECONDS})
    assert purge_idle_sessions(db, retention_days=7, now=now) == 1
    with sqlite3.connect(db) as conn:
        assert [r[0] for r in conn.execute("SELECT id FROM sessions")] == ["recent"]
        assert [r[0] for r in conn.execute("SELECT session_id FROM events")] == ["recent"]


def test_missing_or_empty_store_is_fine(tmp_path):
    assert purge_idle_sessions(tmp_path / "absent.db", 7) == 0
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    assert purge_idle_sessions(empty, 7) == 0
