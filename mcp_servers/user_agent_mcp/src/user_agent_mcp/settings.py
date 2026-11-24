"""Settings from environment variables (listed in the README)."""

import base64
import binascii
import os
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
        return cls(
            env=e.get("SDLC_ENV", "local"),
            config_source=e["CONFIG_SOURCE"],
            store_root=Path(e["STORE_MOUNT_PATH"]),
            public_url=e.get("PUBLIC_URL", f"http://localhost:{e.get('PORT', '8080')}").rstrip("/"),
            sdlc_ui_url=(e.get("SDLC_UI_URL") or "").rstrip("/") or None,
            encryption_key=key,
            encryption_key_version=e.get("DATA_ENCRYPTION_KEY_VERSION", "1"),
            config_refresh_seconds=float(e.get("CONFIG_REFRESH_SECONDS", "30")),
        )
