---
name: design-review
description: Review a technical design for correctness, risks, operability and security before it is approved (leads).
---

# Design review

Use this skill when a lead asks for a review of a design document or proposal.

## Checklist
1. **Problem and scope:** is the problem clear? Are non-goals stated?
2. **Architecture:** components, data flow, and why this option over the alternatives.
3. **Data:** ownership, classification, retention, migrations and rollback.
4. **Security:** authentication, authorization (deny by default), secrets, audit logging.
5. **Operability:** failure modes, timeouts, retries, observability, on-call impact.
6. **Delivery:** incremental stages, feature flags, test strategy, exit criteria.

## Output
A short verdict (`approve`, `approve with changes`, `needs rework`), then findings grouped as
**blocking**, **should fix**, **nice to have**, each with a concrete suggestion. If an
`approve_design` tool is available and the verdict is `approve`, offer to record the approval.
