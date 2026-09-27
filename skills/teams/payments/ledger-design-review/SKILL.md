---
name: ledger-design-review
description: Review a design that changes the payments ledger (double-entry integrity, idempotency, reconciliation) - payments leads.
---

# Ledger design review (payments leads)

Use this skill when a payments lead reviews a design that changes how money movements are recorded.

## Checklist
1. **Double entry:** every movement posts balanced debit and credit entries; no in-place edits.
2. **Idempotency:** retries cannot post twice (idempotency keys, unique constraints).
3. **Ordering and concurrency:** posting order and balance checks are safe under concurrency.
4. **Reconciliation:** how the ledger reconciles with processors and banks; how breaks surface.
5. **Corrections:** reversals and adjustments are new entries, fully audited.
6. **Migration:** backfill and cutover plan with verification totals before and after.

Give a verdict and list blocking issues first.
