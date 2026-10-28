# sdlc_secrets

Secret references resolved at runtime (version-01 §4.2). Config **names** a secret and never holds its value.

| Reference | Read from |
|---|---|
| `{ env: NAME }` | the process environment (`.env` locally, Cloud Run env on GCP) |
| `{ secret: name }` | the configured store: `SDLC_SECRET_<NAME>` with the `env` backend; Google Secret Manager (latest version) with the `gcp` backend |

```python
from sdlc_secrets import resolver_from_env

secrets = resolver_from_env()                      # one per process
token = secrets.resolve({"secret": "jira-payments-token"})
headers = {"Authorization": f"Bearer {token.reveal()}"}   # reveal only at the point of use
...
secrets.invalidate({"secret": "jira-payments-token"})     # after a 401: re-read once
```

- Backend selection is environment configuration: `SDLC_SECRETS_BACKEND=env|gcp` (default `env`),
  `SDLC_SECRETS_PROJECT` (default `GOOGLE_CLOUD_PROJECT`), `SDLC_SECRETS_LOCATION` (regional secrets; unset = global).
- `gcp` uses the Secret Manager REST API with Application Default Credentials (the service identity on Cloud Run,
  gcloud ADC locally; `GOOGLE_CLOUD_QUOTA_PROJECT` is sent as the quota project). The caller needs
  `roles/secretmanager.secretAccessor` on each secret it reads.
- Values are cached per reference for 5 minutes, so rotation needs no redeploy.
- `SecretValue` has a masked `repr`/`str` and cannot be pickled. Errors name the secret, never the value.
- Secrets needed before a service can start (DB passwords, Entra values, `groups.yaml`) stay Cloud Run env/file
  mounts; this library is for connector and downstream credentials.

Tests: `tests/secrets/`.
