# sdlc_logging

Structured JSON logging for every service, in the format Cloud Logging reads from stdout
(`severity`, `message`, plus fields), and audit records ([NFR-AUD-001](../../spec/requirements/non-functional/NFR-AUD-001.md),
[NFR-AUD-002](../../spec/requirements/non-functional/NFR-AUD-002.md)).

- `configure_logging(service)`: one JSON object per line on stdout, with `service` on every entry.
- `audit(event, **fields)`: an audit record tagged `log_type: sdlc_audit`, so one filter selects all audit records.
  Never pass tokens, secrets or tool argument values.

| Variable | Default | Meaning |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Minimum level written |
