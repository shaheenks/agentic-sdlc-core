# INC-2031: duplicate refunds after processor timeout (CONFIDENTIAL)

## Summary
On 2026-08-14 a processor timeout caused the refund worker to retry without the original
idempotency key for 42 minutes. 318 customers received a second refund, total 1.9M INR.

## Root cause
A configuration change reset the idempotency key cache on worker restart. Retries generated new
keys, so the processor treated them as new refunds.

## Actions
- Persist idempotency keys with the refund record (done).
- Alert on refund amount per merchant above 3x the daily average (in progress).
- Recovery of duplicate refunds handled by finance; customer list restricted to payments leads.
