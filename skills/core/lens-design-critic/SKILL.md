---
name: lens-design-critic
description: Goldfish review lens. Design critic - unbacked assumptions, failure modes, security, scale and cost.
---

# Lens: design critic

Stress-test the design. Do not accept assertions without a reason.

- **Assumptions:** claims about external systems, data, performance or limits with no evidence.
  If you have knowledge tools, check claims about the organisation's own systems and say what
  you found (or that you found nothing).
- **Failure modes:** what happens on timeouts, partial failure, retries, duplicate requests,
  rollback. Single points of failure.
- **Security:** authentication, authorization (deny by default), secrets, data classification,
  audit logging.
- **Scale and cost:** load, storage growth, quotas, model or token budgets - stated and plausible?
- **Missing sections:** no alternatives considered, no risks, no success measures.

Severity: blocker = a likely outage, data loss or security gap; major = an unmitigated risk or an
unbacked core assumption; nit = could be clearer.
