# Design: automatic retries for failed refunds

## Summary
Refunds that fail with a timeout from the card processor are retried automatically up to three
times with exponential backoff, instead of waiting for an operator.

## Proposal
1. `payments-api` writes every failed refund to a new `refund_retries` table: refund id,
   merchant id, amount, currency, the full card number and expiry (so the retry can be sent
   without calling the vault again), the processor error and the attempt count.
2. A worker polls the table every minute and resends due refunds to the processor.
3. Each attempt is logged at INFO with the whole request body, for debugging.
4. After the third failure the refund is marked `needs_operator` and an alert is raised.

## Rollout
Behind the flag `refund_auto_retry`, first for one pilot merchant, then for everyone.

## Risks
- Duplicate refunds if the processor applied a refund that timed out: the processor's
  idempotency key is reused for every attempt.
