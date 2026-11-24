---
type: Functional Requirement
title: "Activation per environment"
description: "A bundle becomes active in an environment through an explicit, audited action."
tags: [requirement, configuration]
status: draft
x-area: CFG
x-priority: must
x-implementation: planned
---

# Statement

The system shall activate a configuration bundle in an environment only through an explicit, audited action, and allow the previous version to be reactivated.

# Acceptance criteria

- Activating a version updates the object naming the active version in the configuration bucket.
- Activation records who activated which version, where and when.
- Running services pick up a newly active bundle without a redeploy.
- Reactivating the previous version restores its behaviour.
