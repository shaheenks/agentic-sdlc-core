# Payments alerts

## RefundAmountSpike
Fires when the refunded amount for one merchant exceeds 3x its 30-day daily average within an
hour. Routed to the refund-worker's pager rotation. First step: pause the refund-worker queue
with `refundctl pause`, then check for duplicate idempotency keys.

## ProcessorTimeouts
Fires when more than 2% of processor-gateway calls time out over 5 minutes. Refunds are retried
automatically; payments are failed fast. Check the processor status page before escalating.

## LedgerPostingLag
Fires when ledger-service postings lag payment state changes by more than 60 seconds.
