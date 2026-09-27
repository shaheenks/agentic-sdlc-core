"""A throwaway `sdlc_test` database with the real roles, migrations and RLS (tests only).

Setup (database, extension, schema) uses the local dev superuser; everything the tests exercise
runs as the real roles: sdlc_owner (migrate), sdlc_ingest (ingest), sdlc_app (queries).
Needs the Postgres container and the .env passwords (run: uv run --env-file .env pytest).
"""

import os

import psycopg
from psycopg import sql
from sdlc_db import conninfo
from sdlc_db.migrate import migrate

TEST_DB = "sdlc_test"


def available() -> str | None:
    """None if the test database can be built, else the reason to skip."""
    for var in (
        "POSTGRES_SUPERUSER_PASSWORD",
        "SDLC_OWNER_PASSWORD",
        "SDLC_INGEST_PASSWORD",
        "PGPASSWORD",
    ):
        if not os.environ.get(var):
            return f"{var} not set (run with --env-file .env)"
    try:
        with psycopg.connect(_superuser("postgres"), connect_timeout=3):
            return None
    except psycopg.OperationalError as e:
        return f"Postgres not reachable: {e}".splitlines()[0]


def _superuser(dbname: str) -> str:
    return conninfo(
        "app", user="postgres", password=os.environ["POSTGRES_SUPERUSER_PASSWORD"], dbname=dbname
    )


def create_test_database() -> None:
    app_user = os.environ.get("PGUSER", "sdlc_app")
    with psycopg.connect(_superuser("postgres"), autocommit=True) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(TEST_DB))
        )
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB)))
    with psycopg.connect(_superuser(TEST_DB), autocommit=True) as db:
        db.execute("CREATE EXTENSION IF NOT EXISTS vector")
        db.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        db.execute("CREATE SCHEMA sdlc AUTHORIZATION sdlc_owner")
        for role in ("sdlc_owner", app_user, "sdlc_ingest"):
            ident = sql.Identifier(role)
            db.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(TEST_DB), ident)
            )
            db.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(ident))
        for role in (app_user, "sdlc_ingest"):
            db.execute(sql.SQL("GRANT USAGE ON SCHEMA sdlc TO {}").format(sql.Identifier(role)))
    migrate(conninfo("owner", dbname=TEST_DB))


def db_conninfo(role: str) -> str:
    return conninfo(role, dbname=TEST_DB)


# --- shared helpers for tests/db ----------------------------------------------------------------


def run(coro):
    """psycopg async needs a selector loop on Windows."""
    import asyncio
    import sys

    if sys.platform == "win32":
        return asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)
    return asyncio.run(coro)


async def ingest_as_ingest_role(snapshot, repo_root, embedder, extractor, sources=None, **kw):
    from sdlc_ingest.pipeline import ingest

    async with await psycopg.AsyncConnection.connect(
        db_conninfo("ingest"), autocommit=True
    ) as conn:
        return await ingest(conn, snapshot, embedder, repo_root, sources, extractor=extractor, **kw)


def app_query(sql_text: str, policy=None, params=()):
    """Run one query as sdlc_app, with the policy's RLS context (or none)."""
    from sdlc_db import rls_settings

    with psycopg.connect(db_conninfo("app")) as conn:
        if policy is not None:
            allowed, rank = rls_settings(policy)
            conn.execute(
                "SELECT set_config('app.allowed_sources', %s, true),"
                " set_config('app.max_classification_rank', %s, true)",
                (allowed, rank),
            )
        return conn.execute(sql_text, params).fetchall()


def superuser_query(sql_text: str, params=()):
    """Unfiltered view for assertions about what was written (superuser bypasses RLS)."""
    with psycopg.connect(_superuser(TEST_DB)) as conn:
        conn.execute("SET search_path = sdlc, public")
        return conn.execute(sql_text, params).fetchall()
