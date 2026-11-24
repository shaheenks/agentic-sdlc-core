---
type: Non-Functional Requirement
title: "Single region europe-west3"
description: "The platform runs and keeps its data in europe-west3 (Frankfurt), with listed exceptions only."
tags: [requirement, hosting]
status: draft
x-area: HOST
x-priority: must
x-implementation: planned
---

# Statement

The system shall run all of its regional resources and store all platform data in europe-west3 (Frankfurt), except where a Google service it uses offers no single-region location.

# Acceptance criteria

- Every regional resource in Terraform is created in europe-west3.
- Agent deployments on Gemini Enterprise Platform (Agent Runtime) are in europe-west3.
- The only exceptions are the ones listed here, each in the closest location the service offers. The Gemini Enterprise app runs in the `eu` multi-region, since it offers only `global`, `us` and `eu`. Model calls use the model's europe-west3 endpoint where it has one and the `eu` endpoint otherwise.
- No platform data is stored or processed in the `global` location unless a decision record approves it for a named model.

# Notes

Agent Runtime supports europe-west3, and an ADK agent registered in an `eu` Gemini Enterprise app may run in any `europe-` region. A model not offered in the app's location is routed to `global`, which has no data residency.

# Citations

[1] [Supported locations for agents in Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/agent-locations)
[2] [Data residency for Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs/locations)
