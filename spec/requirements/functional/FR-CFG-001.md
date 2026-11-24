---
type: Functional Requirement
title: "Versioned configuration bundles"
description: "Configuration is loaded only from validated, versioned bundles."
tags: [requirement, configuration]
status: draft
x-area: CFG
x-priority: must
x-implementation: built
---

# Statement

The system shall load configuration only from validated, versioned bundles and record the version behind every decision.

# Acceptance criteria

- A configuration that fails validation cannot be published.
- A service refuses to start with an invalid or unverifiable bundle.
- Every audit record carries the bundle version.
- Bundles are compiled from the YAML in `config/` ([FR-CFG-004](FR-CFG-004.md)) and published to the configuration bucket ([FR-CFG-005](FR-CFG-005.md)).
