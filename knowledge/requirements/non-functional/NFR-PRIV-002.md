---
type: Non-Functional Requirement
title: Hidden resources are not disclosed
description: A caller cannot tell a resource they may not see from one that does not exist.
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
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

The system shall answer for a resource the caller may not see exactly as for one that does not exist.

# Acceptance criteria

- A hidden skill answers 'unknown skill' and a team the caller is not in answers 'unknown team'.
- Another user's artifact answers 'artifact not found' and another user's thread answers 404.
- Hidden tool and skill names are not written to the audit log, only their count.
