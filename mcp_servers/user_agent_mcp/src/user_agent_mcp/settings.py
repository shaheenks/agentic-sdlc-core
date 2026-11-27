"""Settings from environment variables (listed in the README)."""

import base64
import binascii
import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    env: str
    config_source: str
    store_root: Path
    public_url: str
    sdlc_ui_url: str | None
    encryption_key: bytes | None
    encryption_key_version: str
    config_refresh_seconds: float = 30.0
    knowledge_search_url: str | None = None
    knowledge_auth: str = "id_token"  # or none, in the local environment only
    # The credential-free Code Workspace (DEC-0016): `job` runs the Cloud Run job named by workspace_job; `local`
    # runs it in this process (local environment only); empty: workspace_build is unavailable.
    workspace_mode: str = ""
    workspace_job: str = ""
    workspace_timeout_seconds: int = 1200

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "Settings":
        e = os.environ if environ is None else environ
        missing = [k for k in ("CONFIG_SOURCE", "STORE_MOUNT_PATH") if not e.get(k)]
        if missing:
            raise SystemExit(f"{', '.join(missing)} must be set (fail closed)")
        key = None
        if e.get("DATA_ENCRYPTION_KEY"):
            try:
                key = base64.b64decode(e["DATA_ENCRYPTION_KEY"], validate=True)
            except binascii.Error as exc:
                raise SystemExit("DATA_ENCRYPTION_KEY must be base64") from exc
            if len(key) != 32:
                raise SystemExit("DATA_ENCRYPTION_KEY must be 32 bytes (AES-256)")
        env = e.get("SDLC_ENV", "local")
        knowledge_auth = e.get("KNOWLEDGE_AUTH", "id_token")
        knowledge_url = (e.get("KNOWLEDGE_SEARCH_URL") or "").rstrip("/") or None
        if knowledge_auth not in ("id_token", "none") or (
            knowledge_auth == "none" and env != "local" and knowledge_url
        ):
            raise SystemExit("KNOWLEDGE_AUTH must be id_token, or none in the local environment (fail closed)")
        mode = e.get("WORKSPACE_MODE", "")
        if mode not in ("", "job", "local") or (mode == "local" and env != "local"):
            raise SystemExit("WORKSPACE_MODE must be job, or local in the local environment (fail closed)")
        if mode == "job" and not re.match(r"^projects/[^/]+/locations/[^/]+/jobs/[^/]+$", e.get("WORKSPACE_JOB", "")):
            raise SystemExit("WORKSPACE_JOB must be projects/<p>/locations/<r>/jobs/<name> (fail closed)")
        return cls(
            env=env,
            config_source=e["CONFIG_SOURCE"],
            store_root=Path(e["STORE_MOUNT_PATH"]),
            public_url=e.get("PUBLIC_URL", f"http://localhost:{e.get('PORT', '8080')}").rstrip("/"),
            sdlc_ui_url=(e.get("SDLC_UI_URL") or "").rstrip("/") or None,
            encryption_key=key,
            encryption_key_version=e.get("DATA_ENCRYPTION_KEY_VERSION", "1"),
            config_refresh_seconds=float(e.get("CONFIG_REFRESH_SECONDS", "30")),
            knowledge_search_url=knowledge_url,
            knowledge_auth=knowledge_auth,
            workspace_mode=mode,
            workspace_job=e.get("WORKSPACE_JOB", ""),
            workspace_timeout_seconds=int(e.get("WORKSPACE_TIMEOUT_SECONDS", "1200")),
        )
