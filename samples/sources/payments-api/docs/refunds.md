# Refunds

## Flow
A refund request is validated against the captured amount, recorded as `refund_pending`, and
sent to the card processor. The processor callback moves it to `refunded` or `refund_failed`.

## Retries
Refunds are retried by the refund worker with exponential backoff (30s, 2m, 10m, 1h), at most
five attempts. Each attempt reuses the original idempotency key so the processor never issues a
refund twice. After the last attempt the refund goes to the `refund_manual_review` queue.

## Partial refunds
Several partial refunds are allowed while their sum stays at or below the captured amount.
