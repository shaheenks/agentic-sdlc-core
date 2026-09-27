"""Row-level-security context per transaction.

`scoped(conn, policy)` opens a transaction and sets (SET LOCAL semantics via set_config):
  app.allowed_sources          the caller's readable sources: granted by Source.access AND at
                               or below the ceiling by the current config (readable_sources)
  app.max_classification_rank  the caller's classification ceiling (checked again per row)
The policies in db/migrations/001_knowledge.sql filter every row on both. The settings end with
the transaction, so a pooled connection never carries one user's scope into another request.
"""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from sdlc_config import EffectivePolicy

_SOURCE_ID = re.compile(r"^[a-z][a-z0-9-]*$")  # same rule as the Source schema


def rls_settings(policy: EffectivePolicy) -> tuple[str, str]:
    """(allowed_sources array literal, max rank) for set_config. Source ids are validated so the
    array literal cannot be broken out of."""
    ids = list(policy.readable_sources)
    for sid in ids:
        if not _SOURCE_ID.match(sid):
            raise ValueError(f"invalid source id in policy: {sid!r}")
    return "{" + ",".join(ids) + "}", str(policy.max_classification_rank)


@asynccontextmanager
async def scoped(conn: AsyncConnection, policy: EffectivePolicy) -> AsyncIterator[AsyncConnection]:
    allowed, rank = rls_settings(policy)
    async with conn.transaction():
        await conn.execute(
            "SELECT set_config('app.allowed_sources', %s, true),"
            " set_config('app.max_classification_rank', %s, true)",
            (allowed, rank),
        )
        yield conn
