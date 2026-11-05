"""What an artifact may be (version-03 P5): text only, small, with a plain file name.

Downloads are served as attachments with these media types, never rendered on our origin, so
the limits are about abuse and storage, not about making content safe to display.
"""

import re

MAX_BYTES = 1024 * 1024  # 1 MiB per artifact
MAX_LIVE_PER_USER = 50
# media type -> allowed file extensions
MEDIA_TYPES: dict[str, tuple[str, ...]] = {
    "text/markdown": (".md", ".markdown"),
    "text/plain": (".txt",),
    "text/csv": (".csv",),
    "application/json": (".json",),
}
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,99}$")


class ArtifactInputError(ValueError):
    """The caller asked for something an artifact may not be (shown to the caller)."""


def validate(name: str, content: str, media_type: str) -> bytes:
    """Checked UTF-8 bytes of the content, or ArtifactInputError with a plain reason."""
    if media_type not in MEDIA_TYPES:
        allowed = ", ".join(MEDIA_TYPES)
        raise ArtifactInputError(f"media_type must be one of: {allowed}")
    name = name or ""
    if not _NAME.match(name) or ".." in name:
        raise ArtifactInputError(
            "name: 1-100 characters of letters, digits, '.', '_', '-' and spaces, "
            "starting with a letter or digit"
        )
    if not name.lower().endswith(MEDIA_TYPES[media_type]):
        wanted = " or ".join(MEDIA_TYPES[media_type])
        raise ArtifactInputError(f"name must end with {wanted} for {media_type}")
    data = (content or "").encode("utf-8")
    if not data:
        raise ArtifactInputError("content is empty")
    if len(data) > MAX_BYTES:
        raise ArtifactInputError(f"content is larger than {MAX_BYTES // 1024} KiB")
    return data
