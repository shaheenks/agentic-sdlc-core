"""Settings from environment variables (listed in the README)."""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

LOCAL = "local"
QUEUE = re.compile(r"^projects/[^/]+/locations/[^/]+/queues/[^/]+$")


def secret_variable(provider: str) -> str:
    """The environment variable holding a provider's webhook secret: WEBHOOK_SECRET_<PROVIDER>."""
    return "WEBHOOK_SECRET_" + re.sub(r"[^A-Za-z0-9]", "_", provider).upper()


@dataclass(frozen=True)
class Settings:
    env: str
    config_source: str
    public_url: str
    # Deliveries and runs: a bucket (create-if-absent objects under events/), or a folder in the local environment.
    events_bucket: str = ""
    events_dir: Path | None = None
    # Hand-off (DEC-0015): `queue` creates a Cloud Task calling `<public_url>/run` with an OIDC token of
    # tasks_invoker; `inline` starts the run in this process (local environment only).
    tasks_mode: str = "queue"
    tasks_queue: str = ""
    tasks_invoker: str = ""
    # The event agents' Agent Runtime engine: https://<region>-aiplatform.googleapis.com/v1/projects/.../reasoningEngines/<id>
    agent_url: str = ""
    agent_auth: str = "google"  # or none, in the local environment only
    config_refresh_seconds: float = 30.0
    max_body_bytes: int = 1_000_000
    secrets: Mapping[str, str] = field(default_factory=dict, repr=False)

    @property
    def run_url(self) -> str:
        return f"{self.public_url}/run"

    def webhook_secret(self, provider: str) -> bytes | None:
        value = self.secrets.get(secret_variable(provider))
        return value.encode() if value else None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        e = os.environ if environ is None else environ
        env = e.get("SDLC_ENV", LOCAL)
        missing = [k for k in ("CONFIG_SOURCE", "PUBLIC_URL", "AGENT_URL") if not e.get(k)]
        if missing:
            raise SystemExit(f"{', '.join(missing)} must be set (fail closed)")
        if not e.get("EVENTS_BUCKET") and not (e.get("EVENTS_DIR") and env == LOCAL):
            raise SystemExit("EVENTS_BUCKET must be set (EVENTS_DIR in the local environment only; fail closed)")
        mode = e.get("TASKS_MODE", "queue")
        if mode == "queue" and (not QUEUE.match(e.get("TASKS_QUEUE", "")) or "@" not in e.get("TASKS_INVOKER", "")):
            raise SystemExit("TASKS_QUEUE (projects/<p>/locations/<r>/queues/<q>) and TASKS_INVOKER must be set")
        if mode not in ("queue", "inline") or (mode == "inline" and env != LOCAL):
            raise SystemExit("TASKS_MODE must be queue, or inline in the local environment (fail closed)")
        auth = e.get("AGENT_AUTH", "google")
        if auth not in ("google", "none") or (auth == "none" and env != LOCAL):
            raise SystemExit("AGENT_AUTH must be google, or none in the local environment (fail closed)")
        return cls(
            env=env,
            config_source=e["CONFIG_SOURCE"],
            public_url=e["PUBLIC_URL"].rstrip("/"),
            events_bucket=e.get("EVENTS_BUCKET", ""),
            events_dir=Path(e["EVENTS_DIR"]) if e.get("EVENTS_DIR") and not e.get("EVENTS_BUCKET") else None,
            tasks_mode=mode,
            tasks_queue=e.get("TASKS_QUEUE", ""),
            tasks_invoker=e.get("TASKS_INVOKER", ""),
            agent_url=e["AGENT_URL"].rstrip("/"),
            agent_auth=auth,
            config_refresh_seconds=float(e.get("CONFIG_REFRESH_SECONDS", "30")),
            secrets={k: v for k, v in e.items() if k.startswith("WEBHOOK_SECRET_") and v},
        )
