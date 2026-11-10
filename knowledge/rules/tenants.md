---
type: Rule Set
title: Tenant accounts and enterprise tenants
description: "Test users, when the tenant admin account may be used, and keeping identity tenant-agnostic."
tags: [rules]
status: draft
---

Binding working rules for contributors and coding agents, moved word for word from `CLAUDE.md` on 2026-11-10.
Paths are relative to the repository root.

# Tenant accounts

- The dev tenant has test users for sign-in, token and persona checks (payments developer, platform developer,
  admin, and the owner's own account with no sdlc groups). Their UPNs are NOT kept in the repo; pass them on the
  command line (e.g. `entra_setup.ps1 -TestUserA … -TestUserB … -AdminUser …`).
- **The tenant admin account is used only when required and confirmed by the user for that action.** Any Entra
  change (`az ad …`, Graph writes via `az rest`, `entra_setup.ps1` without `-DryRun`) needs that confirmation.
  `az` on the dev machine is usually signed in as the admin: check `az account show` before Entra commands.
  Read-only queries and `-DryRun` are fine, but say which account they run as.

# Enterprise tenants

See "Enterprise Tenant Readiness" (gaps E1–E10) in docs/plans/version-00.md.
- Keep identity tenant-agnostic: tenant/app IDs come from env, group IDs from the git-ignored groups.yaml.
  Never hard-code login/Graph hosts in new code; take them from `platform.yaml` (`identity.authority_host`, `graph_host`;
  the agent web app and oauth2-proxy use `ENTRA_AUTHORITY_HOST`, since agents never read config).
- Don't assume the `groups` claim is present or complete (overage, nested groups, Free-tier `SecurityGroup`).
  Missing groups mean fewer permissions, never more (fail closed). App roles (Stage 3) are the enterprise path.
- Dev-only shortcuts (Azure CLI pre-authorization, client secrets, the PowerShell provisioning script) must not
  leak into prod: prod uses Terraform, certificates or federated credentials, and no Azure CLI pre-auth.
