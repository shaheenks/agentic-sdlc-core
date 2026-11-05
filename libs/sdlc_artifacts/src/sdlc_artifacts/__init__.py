"""Agent-generated artifacts (version-03 P5): content store + limits.
See libs/sdlc_artifacts/README.md.

Only the MCP server uses this. Metadata and ownership live in Postgres (`sdlc_db.artifacts`); this
package stores bytes under `artifacts/<owner oid>/<artifact id>` and checks names, types and sizes.
"""

from sdlc_artifacts.limits import (
    MAX_BYTES,
    MAX_LIVE_PER_USER,
    MEDIA_TYPES,
    ArtifactInputError,
    validate,
)
from sdlc_artifacts.store import (
    ArtifactStore,
    ArtifactStoreError,
    FileArtifactStore,
    GcsArtifactStore,
    MemoryArtifactStore,
    object_key,
    store_from_env,
)

__all__ = [
    "MAX_BYTES",
    "MAX_LIVE_PER_USER",
    "MEDIA_TYPES",
    "ArtifactInputError",
    "ArtifactStore",
    "ArtifactStoreError",
    "FileArtifactStore",
    "GcsArtifactStore",
    "MemoryArtifactStore",
    "object_key",
    "store_from_env",
    "validate",
]
