# payments-api

Service that captures card payments, issues refunds and posts every money movement to the
double-entry ledger. Owned by the payments team.

- Capture: `POST /payments/{id}/capture`
- Refund: `POST /payments/{id}/refunds` (idempotency key required)
- Ledger postings are written in the same transaction as the payment state change.
