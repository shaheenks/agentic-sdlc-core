---
type: Functional Requirement
title: Build and test workflows
description: CI events start pull request analysis, code quality, security audit and change management workflows that report back to source control.
area: Workflows
tags:
- requirement
- functional
- workflows
status: draft
priority: should
implementation: planned
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: change
  resource: ../../changes/CH-0008.md
  title: CH-0008 Workflow platform design baseline
---

# Statement

The system shall analyse pull requests and builds on CI events and report findings back to the source control system.

# Acceptance criteria

- Workflows for pull request analysis, code quality, security audit and change management can be declared and enabled per team.
- Each review runs as isolated passes, one lens skill each, and findings are graded Blocker, Major or Nit.
- Findings are delivered as a PR comment, a check or a Code Insights report, once per PR revision.
- An instruction injected into a PR title, description or diff does not change which tools the workflow calls.

# Notes

Replaces part of FR-AUTO-001. CH-0003 retires the SDLC action stubs (FR-ACT-001).
