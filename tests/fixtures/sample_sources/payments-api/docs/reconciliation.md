# Reconciliation

The reconciliation-job runs nightly at 02:00 IST. It loads the processor settlement file,
matches each settled payment and refund to a ledger posting by idempotency key, and writes
mismatches to the `recon_exceptions` table. Finance reviews exceptions every morning; unresolved
exceptions older than three days page the ledger squad.
