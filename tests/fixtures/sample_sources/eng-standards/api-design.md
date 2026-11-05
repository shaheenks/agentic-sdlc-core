# API design standard

- Resources are nouns, plural (`/payments`, `/deployments`); actions use sub-resources.
- Every mutating endpoint accepts an idempotency key.
- Errors use RFC 9457 problem details. Never leak stack traces.
- Version with a header, not the path; breaking changes need a deprecation window of 90 days.
