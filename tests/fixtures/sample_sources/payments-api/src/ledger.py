"""Double-entry ledger postings (sample code)."""


def post_refund(ledger, refund):
    """Every refund posts a balanced debit/credit pair; entries are never edited in place."""
    ledger.post(
        debit="merchant_balance",
        credit="customer_refunds",
        amount=refund.amount,
        reference=refund.idempotency_key,
    )


def reverse(ledger, entry):
    """Corrections are new reversing entries, fully audited."""
    ledger.post(
        debit=entry.credit,
        credit=entry.debit,
        amount=entry.amount,
        reference=f"reversal:{entry.id}",
    )
