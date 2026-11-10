---
type: Rule Set
title: Environments and endpoints
description: "Development on localhost and the tunnel, GCP dev, hostnames as configuration, and who runs Terraform and deployments."
tags: [rules]
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T22:53:19+05:30'
---

Binding working rules for contributors and coding agents, moved word for word from `CLAUDE.md` on 2026-11-10.
Paths are relative to the repository root.

# Environments and endpoints

See ARCHITECTURE.md §7.
- **Current phase: development.** Local dev runs on localhost + the Cloudflare Tunnel; GCP dev (below) runs on Cloud Run.
  Do not create or change GCP resources unless the user asks.
- **Development** must work on **both** `localhost` (UI :4180, MCP :8080) **and** the Cloudflare Tunnel
  (`app-sdlc-dev` / `mcp-sdlc-dev.shaheenks.co.in`). Keep both oauth2-proxy instances and both Entra callbacks working;
  test changes to sign-in, cookies or URLs on both paths.
- **Higher environments** (staging, prod) are hosted directly: DNS CNAME + managed certificate, no tunnel, no localhost
  callbacks, no Azure CLI pre-authorization.
- **Dev on GCP** (version-01 M7, 2026-10-28): project `sdlc-demo-env01`, region `asia-southeast1`, env `dev`
  (`infra/gcp/dev.tfvars`, state `gs://sdlc-demo-env01-tf-state` prefix `dev`, `config/env/dev/groups.yaml`), Cloud Run
  `*.run.app` URLs (temporary exception to the CNAME rule); the dev callback goes on `sdlc-client`. Public Cloud Run
  services use `invoker_iam_disabled`; Entra stays the gate. The earlier `cloud-migration-agent` / asia-south1 staging
  attempt is abandoned (ignore its state). **The user runs Terraform and the deploy script; do not run `terraform` or
  `gcp_deploy.ps1` yourself** (2026-10-28). Keep `infra/gcp` valid when shared code changes. Runbook: docs/guides/GCP_DEPLOYMENT.md.
- Hostnames and public URLs are configuration (`SDLC_APP_HOST`, `SDLC_MCP_HOST`, `MCP_PUBLIC_URL`), never hard-coded;
  code must not assume `localhost` or a tunnel. Use `<service>-sdlc-<env>.shaheenks.co.in` (one level below the zone).
- After changing Entra redirect URIs, check each entry separately (`az ad app show … -o json`), not the joined TSV output.
