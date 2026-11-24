---
type: Non-Functional Requirement
title: "Separate environments"
description: "Each environment has its own Google Cloud project, configuration and data."
tags: [requirement, hosting]
status: draft
x-area: HOST
x-priority: must
x-implementation: planned
---

# Statement

The system shall run each environment (at least development and production) in its own Google Cloud project, with its own active configuration and data.

# Acceptance criteria

- No environment reads another environment's data, secrets or configuration.
- Promoting a release between environments uses the same images and a configuration bundle activated in the target.
- For now only the development environment exists on Google Cloud, alongside local Docker Compose; production is added later.
