---
name: pci-checklist
description: Check a payments change against PCI DSS-driven engineering rules (card data, logging, access, keys).
---

# PCI checklist (payments team)

Use this skill for any change that touches card or payment data, payment APIs or their
infrastructure.

## Check each item and report pass / fail / not applicable
1. **Card data:** no PAN, CVV or full track data stored or logged; PAN masked (first 6 / last 4 at most).
2. **Scope:** the change stays inside the cardholder-data environment boundary, or reduces it.
3. **Transport:** TLS 1.2+ for every hop carrying payment data.
4. **Keys and secrets:** from the approved key management service; nothing in code or config.
5. **Access:** least privilege; access to payment data is logged and reviewed.
6. **Logging:** security events logged without sensitive data; logs retained per policy.
7. **Change control:** peer review and a rollback plan exist.

End with the list of failed items and the fix for each. If anything is unclear, mark it
`needs evidence` rather than guessing.
