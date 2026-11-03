"""Client for processor-gateway (sample code)."""

TIMEOUT_SECONDS = 8
CIRCUIT_OPEN_AFTER_FAILURES = 20


class ProcessorClient:
    """Calls processor-gateway; every refund call carries the refund's idempotency key."""

    def __init__(self, http, base_url="http://processor-gateway"):
        self.http, self.base_url = http, base_url

    def refund(self, refund):
        return self.http.post(
            f"{self.base_url}/refunds",
            json={"amount": refund.amount, "payment": refund.payment_id},
            headers={"Idempotency-Key": refund.idempotency_key},
            timeout=TIMEOUT_SECONDS,
        )
