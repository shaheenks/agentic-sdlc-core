"""Row-level-security context per transaction.

`scoped(conn, policy)` opens a transaction and sets (SET LOCAL semantics via set_config):
  app.allowed_sources          the caller's readable sources: granted by Source.access AND at
                               or below the caller's ceiling for that source (readable_sources)
  app.source_ceilings          JSON: source id -> the caller's ceiling rank for that source
                               (platform roles + roles held in the source's owner team, CH-0009);
                               every row is checked against the ceiling of its own source
  app.max_classification_rank  the highest ceiling (kept for compatibility; no policy uses it)
The policies in db/migrations (001, 002, 008) filter every row on the first two. The settings end
with the transaction, so a pooled connection never carries one user's scope into another request.
"""

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from sdlc_config import EffectivePolicy

_SOURCE_ID = re.compile(r"^[a-z][a-z0-9-]*$")  # same rule as the Source schema

# Parameters: rls_settings(policy), in order.
SET_RLS_CONTEXT = (
    "SELECT set_config('app.allowed_sources', %s, true),"
    " set_config('app.source_ceilings', %s, true),"
    " set_config('app.max_classification_rank', %s, true)"
)


def rls_settings(policy: EffectivePolicy) -> tuple[str, str, str]:
    """(allowed_sources array literal, source ceilings JSON, max rank) for SET_RLS_CONTEXT. Source
    ids are validated so the array literal cannot be broken out of."""
    ids = list(policy.readable_sources)
    for sid in ids:
        if not _SOURCE_ID.match(sid):
            raise ValueError(f"invalid source id in policy: {sid!r}")
    ceilings = {sid: policy.source_ceiling_ranks[sid] for sid in ids}
    return "{" + ",".join(ids) + "}", json.dumps(ceilings), str(policy.max_classification_rank)


@asynccontextmanager
async def scoped(conn: AsyncConnection, policy: EffectivePolicy) -> AsyncIterator[AsyncConnection]:
    settings = rls_settings(policy)
    async with conn.transaction():
        await conn.execute(SET_RLS_CONTEXT, settings)
        yield conn
