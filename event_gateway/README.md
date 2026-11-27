# event_gateway

Receives, verifies, deduplicates and triages events, and starts unattended runs
([component](../spec/components/event-gateway.md), [DEC-0015](../spec/decisions/DEC-0015.md)). Cloud Run service.

- `POST /webhooks/github` (public): the `X-Hub-Signature-256` HMAC is checked with `WEBHOOK_SECRET_GITHUB` before
  anything else. A verified delivery is matched against `subscriptions.yaml` of the active configuration, for the
  teams in `system.yaml` only. A match claims the delivery under `events/deliveries/` (create-if-absent: a
  redelivery starts nothing) and queues one Cloud Task per subscription, named after the delivery; the answer is
  `202` at once.
- `GET /simulate`, `POST /simulate` (sdlc_ui only; [DEC-0016](../spec/decisions/DEC-0016.md)): simulated events
  until the webhooks are set up. sdlc_ui proves itself with its ID token for `PUBLIC_URL` and forwards the user, who
  must be a member of a team in `simulation.teams` of `system.yaml`. `GET` lists the subscriptions they may send;
  `POST` takes `{team, subscription, repository, number}` for a pull request event and reads its branches and merge
  from the provider with `SYSTEM_TOKEN_<PROVIDER>`. The event, with a delivery ID `sim-<hash of its facts>`, then
  takes the webhook's path, marked `simulated` with the user's ID.
- `POST /run` (the queue only): accepts a Google ID token for `<PUBLIC_URL>/run` of `TASKS_INVOKER`, creates the
  run's session on the event agents' Agent Runtime once (kept under `events/runs/`, so a retried task continues it)
  with the team, subscription, run ID, event and inputs in its state, and follows the run to its end within the
  subscription's minutes.

Every delivery received, matched, ignored, duplicated or rejected, and every run started and finished, is audited
with its metadata; payloads and secrets never are.

Build and test from this folder: `uv run pytest`.

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `8084` | Port to listen on (Cloud Run sets it) |
| `SDLC_ENV` | `local` | Environment name |
| `CONFIG_SOURCE` | - | Configuration bucket (`gs://...`) or folder; required |
| `PUBLIC_URL` | - | This service's URL; `/run` is the tasks' target and their tokens' audience; required |
| `WEBHOOK_SECRET_<PROVIDER>` | - | A provider's webhook secret, for example `WEBHOOK_SECRET_GITHUB` (Secret Manager) |
| `SYSTEM_TOKEN_<PROVIDER>` | - | The machine user's token, for example `SYSTEM_TOKEN_GITHUB`: reads pull requests for simulated events (Secret Manager) |
| `EVENTS_BUCKET` | - | Bucket for `events/` (deliveries and runs); `EVENTS_DIR`, a folder, in the local environment only |
| `TASKS_MODE` | `queue` | `queue` (Cloud Tasks) or `inline` (in process, local environment only) |
| `TASKS_QUEUE` | - | `projects/<p>/locations/<r>/queues/<q>` |
| `TASKS_INVOKER` | - | The service account the tasks' OIDC tokens are for (the gateway's own) |
| `AGENT_URL` | - | The event agents' engine: `https://<region>-aiplatform.googleapis.com/v1/projects/<p>/locations/<r>/reasoningEngines/<id>` |
| `AGENT_AUTH` | `google` | `google`, or `none` in the local environment only |
| `CONFIG_REFRESH_SECONDS` | `30` | How often the active bundle is re-checked |
| `LOG_LEVEL` | `INFO` | Minimum log level |
