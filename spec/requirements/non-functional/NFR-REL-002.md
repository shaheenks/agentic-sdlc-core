---
type: Non-Functional Requirement
title: "Multi-zone production"
description: "Production survives the loss of one zone in europe-west3."
tags: [requirement, reliability]
status: draft
x-area: REL
x-priority: must
x-implementation: planned
---

# Statement

The system shall run production across multiple zones of europe-west3, so that losing one zone does not stop the platform or lose committed data.

# Acceptance criteria

- Stateful production services are zone-redundant: for example, the database runs highly available across two zones, and storage buckets are regional.
- Compute services are regional services that place instances across zones, or run at least two instances in different zones.
- Non-production environments may be single-zone.
