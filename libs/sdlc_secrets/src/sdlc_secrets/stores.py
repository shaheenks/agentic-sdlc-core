"""Secret stores: where `{ secret: name }` references are read from.

  EnvSecretStore   SDLC_SECRET_<NAME> from the environment (local dev, CI)
  GcpSecretStore   Google Secret Manager (latest version), global or regional secrets, through the
                   REST API with ADC / the service identity. No client library: google-auth + httpx.

Errors never carry secret values; Secret Manager error bodies are not included either.
"""

import base64
import os
from collections.abc import Callable, Mapping
from typing import Protocol

import httpx

CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class SecretError(RuntimeError):
    pass


class SecretNotFound(SecretError):
    pass


class SecretAccessDenied(SecretError):
    pass


class SecretStore(Protocol):
    name: str  # backend name, for diagnostics

    def get(self, name: str) -> str:
        """The current value of secret `name`. Raises SecretNotFound / SecretError."""
        ...


def env_var_for(name: str) -> str:
    """`atlassian-payments-token` -> `SDLC_SECRET_ATLASSIAN_PAYMENTS_TOKEN`."""
    return "SDLC_SECRET_" + name.upper().replace("-", "_")


class EnvSecretStore:
    name = "env"

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = os.environ if environ is None else environ

    def get(self, name: str) -> str:
        var = env_var_for(name)
        value = self._environ.get(var, "")
        if not value:
            raise SecretNotFound(f"secret '{name}' not found (environment variable {var} not set)")
        return value


def _adc_token_provider() -> Callable[[], str]:
    """Bearer tokens from Application Default Credentials (gcloud ADC locally, the service
    identity on Cloud Run), refreshed when they expire."""
    import google.auth
    import google.auth.transport.requests

    credentials, _ = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])
    request = google.auth.transport.requests.Request()

    def token() -> str:
        if not credentials.valid:
            credentials.refresh(request)
        return credentials.token

    return token


class GcpSecretStore:
    name = "gcp"

    def __init__(
        self,
        project: str,
        location: str | None = None,
        *,
        token_provider: Callable[[], str] | None = None,
        transport: httpx.BaseTransport | None = None,
        quota_project: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not project:
            raise SecretError("GcpSecretStore needs a project")
        self.project, self.location = project, location
        self._token = token_provider
        self._quota_project = quota_project
        self._client = httpx.Client(
            transport=transport, timeout=timeout, follow_redirects=False, trust_env=True
        )

    def _url(self, name: str) -> str:
        if self.location:  # regional secret: regional endpoint (data stays in the region)
            host = f"https://secretmanager.{self.location}.rep.googleapis.com"
            parent = f"projects/{self.project}/locations/{self.location}"
        else:
            host, parent = "https://secretmanager.googleapis.com", f"projects/{self.project}"
        return f"{host}/v1/{parent}/secrets/{name}/versions/latest:access"

    def get(self, name: str) -> str:
        if self._token is None:
            self._token = _adc_token_provider()
        headers = {"Authorization": f"Bearer {self._token()}"}
        if self._quota_project:
            headers["x-goog-user-project"] = self._quota_project
        where = f"secret '{name}' in project {self.project}" + (
            f" ({self.location})" if self.location else ""
        )
        try:
            response = self._client.get(self._url(name), headers=headers)
        except httpx.HTTPError as e:
            raise SecretError(f"{where}: Secret Manager unreachable ({type(e).__name__})") from None
        if response.status_code == 404:
            raise SecretNotFound(f"{where}: not found")
        if response.status_code in (401, 403):
            raise SecretAccessDenied(f"{where}: access denied ({response.status_code})")
        if response.status_code != 200:
            raise SecretError(f"{where}: Secret Manager returned {response.status_code}")
        try:
            data = response.json()["payload"]["data"]
            return base64.b64decode(data).decode("utf-8")
        except (KeyError, ValueError, TypeError):
            raise SecretError(f"{where}: unexpected Secret Manager response") from None
