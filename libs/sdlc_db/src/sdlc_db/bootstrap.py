"""Database bootstrap: extension, roles, schema and grants (idempotent).

The Python equivalent of db/bootstrap/*.sql|sh, for databases without an init hook (Cloud SQL) and
for the test database. Runs as the admin user (`conninfo("admin")`): the local superuser, or Cloud
SQL's `postgres` (a member of cloudsqlsuperuser, which is NOT a superuser: it must be granted
membership of sdlc_owner before it can create a schema owned by it).

  sdlc_owner  - owns schema `sdlc` and its tables; runs migrations (sdlc-db migrate)
  <app user>  - MCP server: read-only, row-level security always applies (PGUSER, default sdlc_app)
  sdlc_ingest - ingest: writes knowledge
None is a superuser or has BYPASSRLS; tables use FORCE ROW LEVEL SECURITY (migrations).
Passwords come from the environment and are re-applied on every run.
"""

import os

import psycopg
from psycopg import sql

ROLE_ATTRS = "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"


def role_passwords() -> dict[str, str]:
    """role -> password from the environment (fails if any is missing)."""
    wanted = {
        "sdlc_owner": "SDLC_OWNER_PASSWORD",
        os.environ.get("PGUSER", "sdlc_app"): "PGPASSWORD",
        "sdlc_ingest": "SDLC_INGEST_PASSWORD",
    }
    missing = [var for var in wanted.values() if not os.environ.get(var)]
    if missing:
        raise RuntimeError(f"bootstrap needs {', '.join(missing)}")
    return {role: os.environ[var] for role, var in wanted.items()}


def bootstrap(admin_conninfo: str, passwords: dict[str, str] | None = None) -> list[str]:
    """Create or update extension, roles, schema and grants. Returns what was created."""
    passwords = passwords or role_passwords()
    app_user = next(r for r in passwords if r not in ("sdlc_owner", "sdlc_ingest"))
    created: list[str] = []
    with psycopg.connect(admin_conninfo, autocommit=True) as conn:
        dbname = conn.info.dbname
        superuser = conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        is_superuser = superuser.fetchone()[0]
        if not conn.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'").fetchone():
            conn.execute("CREATE EXTENSION vector")
            created.append("extension vector")
        for role, password in passwords.items():
            ident = sql.Identifier(role)
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            if exists:
                # Non-superusers may not even name the SUPERUSER/BYPASSRLS attributes in ALTER
                # ROLE: re-set the password only; the attributes are verified below.
                attrs = ROLE_ATTRS if is_superuser else "LOGIN"
                statement = "ALTER ROLE {} " + attrs + " PASSWORD {}"
            else:
                statement = "CREATE ROLE {} " + ROLE_ATTRS + " PASSWORD {}"
                created.append(f"role {role}")
            conn.execute(sql.SQL(statement).format(ident, sql.Literal(password)))
            conn.execute(sql.SQL("ALTER ROLE {} SET search_path = sdlc, public").format(ident))
        if not is_superuser:  # Cloud SQL: needed to create a schema owned by sdlc_owner
            conn.execute("GRANT sdlc_owner TO current_user")
        if not conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = 'sdlc'").fetchone():
            conn.execute("CREATE SCHEMA sdlc AUTHORIZATION sdlc_owner")
            created.append("schema sdlc")
        conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        for role in passwords:
            ident = sql.Identifier(role)
            conn.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(dbname), ident)
            )
            # pgvector's `vector` type lives in public: usage only, no CREATE there for anyone
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(ident))
        for role in (app_user, "sdlc_ingest"):
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA sdlc TO {}").format(sql.Identifier(role)))
        # Fail closed: RLS is only meaningful if none of the roles can bypass it.
        unsafe = conn.execute(
            "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s) AND (rolsuper OR rolbypassrls)",
            (list(passwords),),
        ).fetchall()
        if unsafe:
            raise RuntimeError(f"roles bypass RLS (superuser/BYPASSRLS): {[r for (r,) in unsafe]}")
    return created
