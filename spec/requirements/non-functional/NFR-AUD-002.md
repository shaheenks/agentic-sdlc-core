---
type: Non-Functional Requirement
title: "Audit retention"
description: "Audit records go to the standard Cloud Logging bucket as structured JSON with a unique tag, kept 30 days."
tags: [requirement, auditability]
status: draft
x-area: AUD
x-priority: should
x-implementation: planned
---

# Statement

The system shall write audit records as structured JSON with a unique tag to the project's standard Cloud Logging bucket, kept for 30 days.

# Acceptance criteria

- Every audit record is one structured JSON log entry carrying a unique tag (for example `log_type: sdlc_audit`), so audit records can be selected from all other logs with one filter.
- Records go to the project's standard (`_Default`) Cloud Logging bucket, with 30-day retention and no lock; there is no dedicated audit bucket.
- No platform service account can modify or delete an audit record.

# Notes

Who may read the audit records (beyond the standard log-viewer roles) is considered later.
