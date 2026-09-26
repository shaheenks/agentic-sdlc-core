"""Postgres readiness: reachable as the non-superuser app role, pgvector installed.

Uses the standard libpq env vars (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD) from .env.
Run: uv run --env-file .env pytest tests/e2e/test_db.py
"""

import os

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not os.environ.get("PGPASSWORD"), reason="PG* env vars not set"),
]


def test_db_has_pgvector_and_app_role_is_not_superuser():
    import psycopg

    with psycopg.connect(connect_timeout=5) as conn:
        server_version = conn.info.server_version
        row = conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        is_superuser = conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        is_superuser = is_superuser.fetchone()[0]
    assert server_version >= 170000, f"expected PostgreSQL 17+, got {server_version}"
    assert row is not None, "pgvector not installed: see db/bootstrap/README.md"
    assert not is_superuser, "app role must not be superuser (superusers bypass RLS)"
