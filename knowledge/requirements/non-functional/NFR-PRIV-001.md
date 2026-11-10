---
type: Non-Functional Requirement
title: No sensitive values in logs or traces
description: Tokens, argument values, prompts, responses and document content never reach logs or traces.
area: Privacy
tags:
- requirement
- non-functional
- privacy
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:30:44+05:30'
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

Logs, audit records and traces shall not contain tokens, argument values, prompts, responses or document content.

# Acceptance criteria

- Audit records carry an argument hash, never argument values or raw tokens.
- Trace spans carry no prompts, responses, tokens or argument values.
- Artifact audit records carry ids, type and size, never the content or file name.
