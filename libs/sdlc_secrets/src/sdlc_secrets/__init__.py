"""Secret references resolved at runtime (version-01 §4.2). See libs/sdlc_secrets/README.md.

Config names a secret and never holds its value:
  { env: NAME }      read from the process environment (`.env` locally)
  { secret: name }   a secret in the configured store: Google Secret Manager on GCP, or the
                     environment variable SDLC_SECRET_<NAME> with the `env` backend (local, CI)

Values come back wrapped in `SecretValue` (masked repr) and are cached briefly, so rotation needs
no redeploy. Callers drop a cached value with `invalidate()` after the downstream rejects it.
"""

from sdlc_secrets.refs import SecretRef, SecretValue
from sdlc_secrets.resolver import SecretResolver, resolver_from_env
from sdlc_secrets.stores import (
    EnvSecretStore,
    GcpSecretStore,
    SecretAccessDenied,
    SecretError,
    SecretNotFound,
    SecretStore,
)

__all__ = [
    "EnvSecretStore",
    "GcpSecretStore",
    "SecretAccessDenied",
    "SecretError",
    "SecretNotFound",
    "SecretRef",
    "SecretResolver",
    "SecretStore",
    "SecretValue",
    "resolver_from_env",
]
