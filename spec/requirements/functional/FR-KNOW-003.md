---
type: Functional Requirement
title: "Ingest status"
description: "Operators see each source's ingest status."
tags: [requirement, knowledge]
status: draft
x-area: KNOW
x-priority: should
x-implementation: built
---

# Statement

The system shall report, per source, the last successful ingest, records stored and errors.

# Acceptance criteria

- An ingest failure for one source does not stop the others, and is reported for that source.
