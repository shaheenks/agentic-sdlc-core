---
name: payments-pci-lens
description: Goldfish review lens (payments team). PCI impact - card data, scope, keys, access and logging in a design or change.
---

# Lens: PCI impact (payments)

Read the document as a payments security reviewer who knows PCI DSS but nothing about this
conversation. Judge only what the document says.

- **Card data:** does the design store, log, cache or send PAN, CVV or track data? Is masking
  (first 6 / last 4 at most) stated wherever card numbers appear?
- **Scope:** does it say whether the change is inside the cardholder-data environment, and does
  it widen that boundary (new services, queues, logs or stores that see card data)?
- **Transport and keys:** TLS 1.2+ on every hop with payment data; keys and secrets from the
  approved key management service, never in code or config.
- **Access:** least privilege for people and services; access to payment data logged.
- **Logging and retention:** security events logged without sensitive data.
- **PCI section:** a design or review touching payment data without an explicit PCI impact
  statement is itself a finding.

Severity: blocker = card data stored or logged unprotected, or scope widened without saying so;
major = a missing PCI impact statement, key handling or access rule; nit = wording.
