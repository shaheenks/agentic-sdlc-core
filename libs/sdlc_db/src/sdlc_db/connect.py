"""Connection strings per database role, from the standard libpq environment (PG*).

app    -> PGUSER / PGPASSWORD (sdlc_app: read-only, RLS)         MCP server
ingest -> sdlc_ingest / SDLC_INGEST_PASSWORD                     ingest service
owner  -> sdlc_owner / SDLC_OWNER_PASSWORD                       sdlc-db migrate
admin  -> PGADMIN_USER (default postgres) / POSTGRES_SUPERUSER_PASSWORD   sdlc-db bootstrap only
"""

import os
from typing import Literal

from psycopg.conninfo import make_conninfo

Role = Literal["app", "ingest", "owner", "admin"]


def conninfo(role: Role = "app", **overrides: str) -> str:
    if role == "app":
        user, password = os.environ.get("PGUSER", "sdlc_app"), os.environ.get("PGPASSWORD", "")
    elif role == "ingest":
        user, password = "sdlc_ingest", os.environ.get("SDLC_INGEST_PASSWORD", "")
    elif role == "owner":
        user, password = "sdlc_owner", os.environ.get("SDLC_OWNER_PASSWORD", "")
    elif role == "admin":
        user = os.environ.get("PGADMIN_USER", "postgres")
        password = os.environ.get("POSTGRES_SUPERUSER_PASSWORD", "")
    else:
        raise ValueError(f"unknown database role '{role}'")
    params = {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": os.environ.get("PGPORT", "5432"),
        "dbname": os.environ.get("PGDATABASE", "sdlc"),
        "user": user,
        "password": password,
        "application_name": f"sdlc-{role}",
    }
    params.update(overrides)
    return make_conninfo(**params)
