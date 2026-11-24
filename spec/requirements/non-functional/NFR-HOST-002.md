---
type: Non-Functional Requirement
title: "Infrastructure as code"
description: "All Google Cloud resources are defined in Terraform."
tags: [requirement, hosting]
status: draft
x-area: HOST
x-priority: must
x-implementation: planned
---

# Statement

The system shall define all of its Google Cloud resources in Terraform.

# Acceptance criteria

- Every Google Cloud resource the platform uses is in Terraform.
- A Terraform plan against a deployed environment shows no drift.
