"""ConfigStore: the active bundle, as a service sees it while answering requests."""

import asyncio
import logging
import threading
import time
from collections.abc import Callable

from sdlc_config_store.bundle import Bundle, ConfigUnavailable, parse_bundle, parse_pointer
from sdlc_config_store.sources import Source, bundle_name

log = logging.getLogger("sdlc.config")


class ConfigStore:
    """Holds the last verified bundle. `current()` re-reads active.json when the last check is older than
    `refresh_seconds` and loads a bundle only when the pointer's stamp changed. A failed read or an
    unverifiable bundle keeps the last verified one; with none, `ConfigUnavailable` is raised."""

    def __init__(
        self,
        source: Source,
        env: str,
        refresh_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.source = source
        self.env = env
        self.refresh_seconds = refresh_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._bundle: Bundle | None = None
        self._stamp: str | None = None
        self._checked: float | None = None
        self.last_error: str | None = None

    def load(self) -> Bundle:
        """Load the active bundle now; raises ConfigUnavailable if there is none that verifies."""
        self._refresh()
        return self.current()

    def _stale(self) -> bool:
        return self._checked is None or self._clock() - self._checked >= self.refresh_seconds

    def current(self) -> Bundle:
        if self._stale():
            self._refresh()
        if self._bundle is None:
            raise ConfigUnavailable(self.last_error or "no configuration bundle is active")
        return self._bundle

    async def acurrent(self) -> Bundle:
        """`current()` for async callers: the occasional read runs in a worker thread."""
        if self._stale():
            await asyncio.to_thread(self._refresh)
        return self.current()

    def _refresh(self) -> None:
        with self._lock:
            if not self._stale():
                return
            self._checked = self._clock()
            try:
                raw, stamp = self.source.read_active()
                if stamp == self._stamp and self._bundle is not None:
                    return
                version = parse_pointer(raw)["version"]
                if self._bundle is None or version != self._bundle.version:
                    bundle = parse_bundle(self.source.read(bundle_name(version)), version, self.env)
                    log.info("configuration bundle %s active (was %s)", version, self.version)
                    self._bundle = bundle
                self._stamp = stamp
                self.last_error = None
            except Exception as exc:  # unreadable or unverifiable, including storage client errors
                self.last_error = f"{type(exc).__name__}: {exc}"
                log.error("configuration not refreshed; keeping version %s: %s", self.version, self.last_error)

    @property
    def version(self) -> str | None:
        return self._bundle.version if self._bundle else None
