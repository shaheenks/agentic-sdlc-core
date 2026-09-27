"""Refund handling for payments-api (sample code)."""

RETRY_DELAYS_SECONDS = [30, 120, 600, 3600]
MAX_ATTEMPTS = 5


def request_refund(payment, amount, idempotency_key):
    """Validate and record a refund, then hand it to the processor."""
    if amount <= 0 or amount > payment.captured_amount - payment.refunded_amount:
        raise ValueError("refund exceeds the refundable amount")
    refund = payment.new_refund(amount=amount, idempotency_key=idempotency_key)
    refund.status = "refund_pending"
    return refund


def next_retry_delay(attempt):
    """Backoff for refund retries; None when the refund must go to manual review."""
    if attempt >= MAX_ATTEMPTS:
        return None
    return RETRY_DELAYS_SECONDS[min(attempt, len(RETRY_DELAYS_SECONDS)) - 1]
