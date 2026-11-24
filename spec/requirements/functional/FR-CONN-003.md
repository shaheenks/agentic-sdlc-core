---
type: Functional Requirement
title: "Downstream systems"
description: "The platform reads and writes source control, issue tracking and documentation systems."
tags: [requirement, connections]
status: draft
x-area: CONN
x-priority: must
x-implementation: planned
---

# Statement

The system shall connect to source-control, issue-tracking and documentation systems through the providers declared in configuration.

# Acceptance criteria

- Each provider is declared with its edition and allowed hosts.
- Each provider supports the read operations the workflows need; write operations are separate tools classed as writes.

# Notes

GitHub, Bitbucket, Jira and Confluence, each in cloud and Data Center editions ([FR-CONN-001](FR-CONN-001.md)); the first phase delivers Jira, GitHub and Bitbucket, and Confluence follows.
