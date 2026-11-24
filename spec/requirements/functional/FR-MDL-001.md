---
type: Functional Requirement
title: "Model classes"
description: "Workflows name a model class; configuration maps it to a concrete model."
tags: [requirement, models]
status: draft
x-area: MDL
x-priority: must
x-implementation: planned
---

# Statement

The system shall let workflows name model classes, mapped to concrete models per environment in configuration.

# Acceptance criteria

- Changing the model behind a class needs only a configuration change.
- A run records the concrete model used for each step.
- Every model, language and embedding, runs on Vertex AI; there is no separate model gateway.
