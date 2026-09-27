# INC-2044: ledger posting lag during database failover (CONFIDENTIAL)

## Summary
On 2026-09-02 a zonal failover of the ledger database made ledger-service postings lag by up to
14 minutes. LedgerPostingLag fired; payments stayed consistent because postings were queued.

## Root cause
The connection pool in ledger-service kept stale connections to the old primary for 12 minutes.

## Actions
- Recycle pool connections on failover events (done).
- Add a failover drill to the quarterly game day (planned).
