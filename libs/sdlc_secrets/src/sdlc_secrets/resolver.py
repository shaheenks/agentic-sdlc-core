"""Resolve secret references with a short cache.

`env:` references read the process environment; `secret:` references go to the store. Values are
cached for `ttl` seconds per reference (default 5 minutes), so a rotated secret is picked up
without a redeploy; `invalidate(ref)` drops one early (e.g. after a 401 from the downstream).

Backend selection is configuration (environment), never code:
  SDLC_SECRETS_BACKEND   env (default) | gcp
  SDLC_SECRETS_PROJECT   GCP project (default: GOOGLE_CLOUD_PROJECT)
  SDLC_SECRETS_LOCATION  region for regional secrets (unset = global secrets)
  GOOGLE_CLOUD_QUOTA_PROJECT  quota project for user ADC (dev machines)
"""

import os
import threading
import time
from collections.abc import Callable, Mapping

from sdlc_secrets.refs import SecretRef, SecretValue
from sdlc_secrets.stores import (
    EnvSecretStore,
    GcpSecretStore,
    SecretError,
    SecretNotFound,
    SecretStore,
)

DEFAULT_TTL_SECONDS = 300.0


class SecretResolver:
    def __init__(
        self,
        store: SecretStore,
        environ: Mapping[str, str] | None = None,
        ttl: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.store = store
        self._environ = os.environ if environ is None else environ
        self._ttl = ttl
        self._clock = clock
        self._cache: dict[SecretRef, tuple[float, SecretValue]] = {}
        self._lock = threading.Lock()

    def resolve(self, ref: "SecretRef | Mapping[str, str] | tuple[str, str]") -> SecretValue:
        ref = SecretRef.parse(ref)
        now = self._clock()
        with self._lock:
            cached = self._cache.get(ref)
            if cached is not None and cached[0] > now:
                return cached[1]
        value = SecretValue(self._read(ref))
        with self._lock:
            self._cache[ref] = (now + self._ttl, value)
        return value

    def invalidate(self, ref: "SecretRef | Mapping[str, str] | tuple[str, str]") -> None:
        with self._lock:
            self._cache.pop(SecretRef.parse(ref), None)

    def _read(self, ref: SecretRef) -> str:
        if ref.kind == "env":
            value = self._environ.get(ref.name, "")
            if not value:
                raise SecretNotFound(f"secret {ref} not found (environment variable not set)")
            return value
        return self.store.get(ref.name)


def resolver_from_env(environ: Mapping[str, str] | None = None) -> SecretResolver:
    environ = os.environ if environ is None else environ
    backend = environ.get("SDLC_SECRETS_BACKEND", "env") or "env"
    if backend == "env":
        store: SecretStore = EnvSecretStore(environ)
    elif backend == "gcp":
        project = environ.get("SDLC_SECRETS_PROJECT") or environ.get("GOOGLE_CLOUD_PROJECT", "")
        if not project:
            raise SecretError("SDLC_SECRETS_BACKEND=gcp needs SDLC_SECRETS_PROJECT")
        store = GcpSecretStore(
            project,
            environ.get("SDLC_SECRETS_LOCATION") or None,
            quota_project=environ.get("GOOGLE_CLOUD_QUOTA_PROJECT") or None,
        )
    else:
        raise SecretError(f"unknown SDLC_SECRETS_BACKEND '{backend}' (env or gcp)")
    return SecretResolver(store, environ)
