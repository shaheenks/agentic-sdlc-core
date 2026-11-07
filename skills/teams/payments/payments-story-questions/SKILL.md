---
name: payments-story-questions
description: Extra brainstorm questions (payments team) for user stories and designs that touch payments.
---

# Brief questions: payments

Ask these in addition to the `egm-brainstorm` questions, only when the work is for the payments
team. Skip any already answered; check the code and runbooks with the knowledge tools first.

1. **Payment flow:** which flow is affected (authorisation, capture, refund, payout, ledger)?
2. **Card data:** does the work see, store or send card data? If yes, the brief notes "PCI
   impact: yes" and the review should include the `payments-pci-lens`.
3. **Money correctness:** amounts, currencies, rounding and idempotency of retries.
4. **Repositories:** `payments-api`, `payments-ui`, or both.
5. **Rollout:** feature flag, merchant pilot, or all at once; how to roll back.

Add the answers to the brief under "Payments".
