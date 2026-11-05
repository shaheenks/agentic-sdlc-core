# payments-api architecture

## Components
- **payments-api**: the HTTP service (capture, refunds). Stateless; runs on the shared
  Kubernetes cluster.
- **refund-worker**: background worker that sends refunds to the card processor and retries
  them. It runs as a job on the platform **job-runner**, not inside payments-api.
- **processor-gateway**: adapter in front of the external card processor. payments-api and the
  refund-worker call it through `processor_client`.
- **ledger-service**: owns the double-entry ledger. payments-api posts every money movement to it
  in the same transaction as the payment state change.
- **reconciliation-job**: nightly job, also on job-runner, that compares ledger postings with the
  processor settlement files.

## Data
Payment and refund records live in the `payments-db` Postgres database. Ledger entries live in
`ledger-db`, which only ledger-service may write.
