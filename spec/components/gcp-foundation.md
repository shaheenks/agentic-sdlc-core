---
type: Component
title: GCP Foundation
description: The Google Cloud base every component runs on - projects per environment, networking, IAM and service accounts, regions and the Terraform that defines them.
tags: [component, platform, infrastructure]
status: draft
x-layer: platform
x-folder: infra/
x-depends-on: []
x-satisfies: [/requirements/functional/FR-IDN-001, /requirements/functional/FR-CFG-005, /requirements/functional/FR-ART-003, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-HOST-002, /requirements/non-functional/NFR-HOST-003, /requirements/non-functional/NFR-HOST-004, /requirements/non-functional/NFR-HOST-005, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-SEC-006, /requirements/non-functional/NFR-SEC-007, /requirements/non-functional/NFR-REL-002]
---

# Purpose

Gives every other component a consistent, reproducible place to run on Google Cloud, so hosting,
identity of services and data location are decided once.

# Responsibilities

- One Google Cloud project per environment, with the APIs the platform uses enabled. For now the only Google
  Cloud environment is development; local development runs on Docker Compose. Staging and production come later.
- Networking: ingress for the surfaces, private access to data stores, egress controls for the outbound allowlist.
- One service account per component, with only the IAM roles it needs.
- Region: every regional resource in europe-west3; production zone-redundant across europe-west3 zones.
- Identity-Aware Proxy on sdlc_ui, the OAuth clients of [DEC-0001](../decisions/DEC-0001.md), and the system identity's service account.
- Buckets: configuration (versioned), artifacts (7-day lifecycle on `artifacts/`, users' encrypted connection
  secrets under `secrets/users/`, IAM conditions per MCP server), trigger deduplication; Secret Manager regional
  secrets for every other secret and the encryption key, wired to services as environment variables; audit records in the standard Cloud Logging bucket (30-day retention).
- Artifact Registry for images; the Terraform that defines all of the above, in folder `infra/`.

# Out of scope

- What runs inside each service: the components themselves.

# Interfaces

- Provides: projects, networks, service accounts, registries and Terraform outputs other components deploy into.

# Depends on

- None.

# Owns

- Terraform state and the environment definitions.

# Requirements

- [FR-IDN-001: Sign-in with Cloud Identity, federated from Entra ID](../requirements/functional/FR-IDN-001.md)
- [FR-CFG-005: Configuration bucket](../requirements/functional/FR-CFG-005.md)
- [FR-ART-003: Artifact retention of 7 days](../requirements/functional/FR-ART-003.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-HOST-002: Infrastructure as code](../requirements/non-functional/NFR-HOST-002.md)
- [NFR-HOST-003: Separate environments](../requirements/non-functional/NFR-HOST-003.md)
- [NFR-HOST-004: Managed services first](../requirements/non-functional/NFR-HOST-004.md)
- [NFR-HOST-005: Single region europe-west3](../requirements/non-functional/NFR-HOST-005.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-SEC-006: Least-privilege service identities](../requirements/non-functional/NFR-SEC-006.md)
- [NFR-SEC-007: sdlc_ui behind Identity-Aware Proxy](../requirements/non-functional/NFR-SEC-007.md)
- [NFR-REL-002: Multi-zone production](../requirements/non-functional/NFR-REL-002.md)

# Realisation

- Terraform with remote state in Cloud Storage; projects per environment.
