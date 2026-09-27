"""Numbered SQL migrations (db/migrations/NNN_name.sql), applied in order as sdlc_owner.

Each file runs in its own transaction and is recorded in sdlc.schema_migrations with a
checksum; editing an applied migration is an error (add a new one instead).
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import psycopg

DEFAULT_DIR = Path(__file__).resolve().parents[4] / "db" / "migrations"


@dataclass(frozen=True)
class Migration:
    version: str  # file name, e.g. "001_knowledge.sql"
    sql: str
    checksum: str


def discover(directory: Path) -> list[Migration]:
    migrations = []
    for path in sorted(directory.glob("[0-9][0-9][0-9]_*.sql")):
        sql = path.read_text(encoding="utf-8")
        migrations.append(Migration(path.name, sql, hashlib.sha256(sql.encode()).hexdigest()))
    return migrations


def migrate(conninfo: str, directory: Path = DEFAULT_DIR) -> list[str]:
    """Apply pending migrations; returns the versions applied."""
    applied_now = []
    with psycopg.connect(conninfo) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sdlc.schema_migrations (
                version    text PRIMARY KEY,
                checksum   text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.commit()
        done = dict(conn.execute("SELECT version, checksum FROM sdlc.schema_migrations").fetchall())
        for migration in discover(directory):
            if migration.version in done:
                if done[migration.version] != migration.checksum:
                    raise RuntimeError(
                        f"{migration.version} was changed after it was applied; "
                        "add a new migration instead"
                    )
                continue
            with conn.transaction():
                conn.execute(migration.sql)
                conn.execute(
                    "INSERT INTO sdlc.schema_migrations (version, checksum) VALUES (%s, %s)",
                    (migration.version, migration.checksum),
                )
            applied_now.append(migration.version)
    return applied_now
