---
name: payments-design-template
description: Document outline (payments team) for a payments design document.
---

# Template: payments design

Use this outline for a design document of the payments team. Keep the headings; leave a
section out only with a one-line reason.

1. **Summary:** the problem and the proposal in three or four sentences.
2. **Context:** current flow, systems involved (`payments-api`, `payments-ui`, others), and
   links to the code or runbooks checked.
3. **Proposal:** the design, with a diagram or numbered flow.
4. **Alternatives considered:** each with why it was not chosen.
5. **PCI impact:** card data seen, stored or sent; cardholder-data environment scope; keys;
   access; logging. Write "none" with a reason if there is none.
6. **Money correctness:** amounts, currencies, rounding, idempotency, reconciliation.
7. **Risks and mitigations.**
8. **Rollout and rollback:** flags, pilot, metrics to watch, how to undo.
9. **Open questions.**
