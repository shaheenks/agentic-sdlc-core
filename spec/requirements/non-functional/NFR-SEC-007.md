---
type: Non-Functional Requirement
title: "sdlc_ui behind Identity-Aware Proxy"
description: "Only signed-in users of the organisation in the declared access groups reach sdlc_ui at all."
tags: [requirement, security]
status: draft
x-area: SEC
x-priority: should
x-implementation: planned
---

# Statement

The system shall put sdlc_ui behind Identity-Aware Proxy, admitting only Cloud Identity users in the access groups declared in configuration.

# Acceptance criteria

- A request that has not passed Identity-Aware Proxy never reaches the sdlc_ui container.
- The BFF verifies the signed IAP header (`x-goog-iap-jwt-assertion`: signature, issuer, audience) on every request and refuses a request without a valid one.
- The access groups come from configuration and are applied by Terraform.

# Notes

Decided in [DEC-0001](../../decisions/DEC-0001.md), accepted by the user on 2026-11-22.

# Citations

[1] [Securing your app with signed headers](https://docs.cloud.google.com/iap/docs/signed-headers-howto)
[2] [IAP integration with Cloud Run](https://cloud.google.com/blog/products/serverless/iap-integration-with-cloud-run)
