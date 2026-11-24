---
type: Functional Requirement
title: "Sign-in with Cloud Identity, federated from Entra ID"
description: "Users are Google accounts in the organisation's Cloud Identity account, signing in through Microsoft Entra ID."
tags: [requirement, identity]
status: draft
x-area: IDN
x-priority: must
x-implementation: built
---

# Statement

The system shall authenticate users as Google accounts in the organisation's Cloud Identity account, which federates sign-in to Microsoft Entra ID, and refuse every request it cannot verify.

# Acceptance criteria

- Users and groups are provisioned from Entra ID into Cloud Identity; the platform keeps no user list of its own.
- Signing in to any surface goes through Entra ID by SAML single sign-on for the Cloud Identity account; users have no Google password.
- The platform accepts only Google-issued tokens that belong to an account of the organisation's Cloud Identity account and were issued to one of the platform's own OAuth clients.
- A request without a valid token gets 401 on every endpoint except health checks and public metadata.
- A user has the same stable user ID, the Google account ID, on every surface.

# Notes

How sdlc_ui signs users in (Identity-Aware Proxy, an OAuth app in the organisation, or both) is decided in [DEC-0001](../../decisions/DEC-0001.md) (accepted).

# Citations

[1] [Federate Google Cloud with Microsoft Entra ID](https://docs.cloud.google.com/architecture/identity/federating-gcp-with-azure-active-directory)
[2] [Microsoft Entra ID user provisioning and single sign-on](https://docs.cloud.google.com/architecture/identity/federating-gcp-with-azure-ad-configuring-provisioning-and-single-sign-on)
