---
type: Non-Functional Requirement
title: "sdlc_ui is one container"
description: "The custom UI and its BFF are built, versioned and deployed as one container named sdlc_ui."
tags: [requirement, architecture]
status: draft
x-area: ARCH
x-priority: must
x-implementation: planned
---

# Statement

The system shall build, version and deploy the custom UI and its backend-for-frontend as a single container image named `sdlc_ui`, running as one service.

# Acceptance criteria

- One image, `sdlc_ui`, contains both the UI build and the BFF.
- UI and BFF are released together under one version; neither is deployed alone.
- The browser talks only to the origin that serves the UI; it calls no other platform service directly.

# Notes

Cloud Run service names cannot contain underscores, so the service is `sdlc-ui`.
