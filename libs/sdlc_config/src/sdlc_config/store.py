"""ConfigStore: holds the current Snapshot, reloads atomically, keeps last-known-good.

Startup fails closed: constructing a store with invalid config raises ConfigError.
Sources: a local config folder (dev, file watching) or a bundle root with a `current` pointer
(sdlc_config.bundles; reload when the pointer moves, rollback = point back). GCS: Stage 7b.
"""

import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path

from sdlc_config.errors import ConfigError
from sdlc_config.loader import load_snapshot
from sdlc_config.model import Snapshot

log = logging.getLogger("sdlc.config")

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[4] / "config"


class ConfigStore:
    def __init__(self, loader: Callable[[], Snapshot], watch_paths: tuple[Path, ...] = ()):
        self._loader = loader
        self._watch_paths = watch_paths
        self._lock = threading.Lock()
        self._subscribers: list[Callable[[Snapshot], None]] = []
        self._stop = threading.Event()
        self.last_error: str | None = None
        self._snapshot = loader()  # raises ConfigError -> service must not start
        log.info("config loaded version=%s env=%s", self._snapshot.version, self._snapshot.env)

    @classmethod
    def from_local(cls, config_dir: Path, env: str) -> "ConfigStore":
        return cls(lambda: load_snapshot(config_dir, env), watch_paths=(config_dir,))

    @classmethod
    def from_bundles(cls, root: Path, env: str) -> "ConfigStore":
        """Serve the bundle `root/current` points at; a pointer move triggers a reload. A broken
        bundle or pointer fails startup, and on reload keeps the last-known-good version."""
        from sdlc_config.bundles import load_bundle

        return cls(lambda: load_bundle(root, env), watch_paths=(root,))

    @classmethod
    def from_env(cls) -> "ConfigStore":
        """SDLC_CONFIG_BUNDLES (a bundle root) if set, else SDLC_CONFIG_DIR (default: repo
        config/); SDLC_ENV (default: local)."""
        env = os.environ.get("SDLC_ENV", "local")
        if os.environ.get("SDLC_CONFIG_BUNDLES"):
            return cls.from_bundles(Path(os.environ["SDLC_CONFIG_BUNDLES"]), env)
        config_dir = Path(os.environ.get("SDLC_CONFIG_DIR", DEFAULT_CONFIG_DIR))
        return cls.from_local(config_dir, env)

    def current(self) -> Snapshot:
        return self._snapshot

    def subscribe(self, callback: Callable[[Snapshot], None]) -> None:
        self._subscribers.append(callback)

    def reload(self) -> bool:
        """Load again. Returns True if a new version was applied; on error keeps the old one."""
        with self._lock:
            try:
                new = self._loader()
            except ConfigError as e:
                self.last_error = str(e)
                log.error(
                    "config reload rejected; keeping version=%s\n%s", self._snapshot.version, e
                )
                return False
            self.last_error = None
            if new.version == self._snapshot.version:
                return False
            old, self._snapshot = self._snapshot.version, new
        log.info("config reloaded version=%s (was %s)", new.version, old)
        for callback in self._subscribers:
            try:
                callback(new)
            except Exception:
                log.exception("config subscriber failed")
        return True

    def start_watching(self) -> threading.Thread:
        """Reload on file changes under the watched paths (local dev). Daemon thread."""
        from watchfiles import watch

        def run() -> None:
            for _ in watch(*self._watch_paths, stop_event=self._stop, debounce=500):
                self.reload()

        thread = threading.Thread(target=run, name="config-watch", daemon=True)
        thread.start()
        return thread

    def stop_watching(self) -> None:
        self._stop.set()
