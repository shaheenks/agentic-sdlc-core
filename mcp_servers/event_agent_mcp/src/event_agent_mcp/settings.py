"""Settings from environment variables (listed in the README)."""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

WORKSPACE_MODES = ("job", "local", "")


def token_variable(provider: str) -> str:
    """The environment variable holding a provider's system connection token: SYSTEM_TOKEN_<PROVIDER>."""
    return "SYSTEM_TOKEN_" + re.sub(r"[^A-Za-z0-9]", "_", provider).upper()


@dataclass(frozen=True)
class Settings:
    env: str
    config_source: str
    store_root: Path
    public_url: str
    config_refresh_seconds: float = 30.0
    # The Code Workspace (DEC-0015): `job` runs the Cloud Run job named by workspace_job; `local` runs it in this
    # process (local environment only); empty: workspace_run is unavailable.
    workspace_mode: str = ""
    workspace_job: str = ""
    workspace_timeout_seconds: int = 1200
    tokens: Mapping[str, str] = field(default_factory=dict, repr=False)  # SYSTEM_TOKEN_* variables, never logged

    def system_token(self, provider: str) -> str | None:
        return self.tokens.get(token_variable(provider)) or None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        e = os.environ if environ is None else environ
        missing = [k for k in ("CONFIG_SOURCE", "STORE_MOUNT_PATH") if not e.get(k)]
        if missing:
            raise SystemExit(f"{', '.join(missing)} must be set (fail closed)")
        env = e.get("SDLC_ENV", "local")
        mode = e.get("WORKSPACE_MODE", "")
        if mode not in WORKSPACE_MODES or (mode == "local" and env != "local"):
            raise SystemExit("WORKSPACE_MODE must be job, or local in the local environment (fail closed)")
        if mode == "job" and not re.match(r"^projects/[^/]+/locations/[^/]+/jobs/[^/]+$", e.get("WORKSPACE_JOB", "")):
            raise SystemExit("WORKSPACE_JOB must be projects/<p>/locations/<r>/jobs/<name> (fail closed)")
        return cls(
            env=env,
            config_source=e["CONFIG_SOURCE"],
            store_root=Path(e["STORE_MOUNT_PATH"]),
            public_url=e.get("PUBLIC_URL", f"http://localhost:{e.get('PORT', '8081')}").rstrip("/"),
            config_refresh_seconds=float(e.get("CONFIG_REFRESH_SECONDS", "30")),
            workspace_mode=mode,
            workspace_job=e.get("WORKSPACE_JOB", ""),
            workspace_timeout_seconds=int(e.get("WORKSPACE_TIMEOUT_SECONDS", "1200")),
            tokens={k: v for k, v in e.items() if k.startswith("SYSTEM_TOKEN_") and v},
        )
