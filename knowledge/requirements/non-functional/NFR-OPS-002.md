---
type: Non-Functional Requirement
title: Continuous deployment to GCP dev
description: Every merge to main deploys to GCP dev from GitHub, running only the deployment steps its changes need, in a fixed order.
area: Operability
tags:
- requirement
- non-functional
- operability
status: draft
priority: should
implementation: planned
sources:
- id: deploy
  resource: ../../../scripts/gcp_deploy.ps1
  title: GCP deployment script
- id: gcp
  resource: ../../../docs/guides/GCP_DEPLOYMENT.md
  title: GCP deployment guide
- id: change
  resource: ../../changes/CH-0010.md
  title: CH-0010 Continuous deployment to GCP dev
---

# Statement

Every merge to `main` shall be deployed to the GCP dev environment by a GitHub workflow that runs, one after another, only the deployment steps that the merged changes need.

# Acceptance criteria

- **Trigger:** a push to `main` (a merged PR) starts the deploy workflow once the `ci` checks pass on that commit. A failed check deploys nothing.
- **Steps:** they always run in this order, and each runs only when its inputs changed since the last successful deploy:
  1. `images`: service code, Dockerfiles or the lock file changed.
  2. `plan` and `apply`: `infra/gcp` changed, or new images were pushed.
  3. `db`: `db/` migrations changed.
  4. `config`: `config/`, `skills/` or the tenant files changed.
  5. `ingest`: `config/sources` changed.
  6. Smoke checks: always.
- **Two scripts, one behaviour:**
  - The workflow runs on the GitHub Linux runners with bash only, through `scripts/gcp_deploy.sh`, which also serves Linux environments.
  - `scripts/gcp_deploy.ps1` stays the script for Windows.
  - Both read the step order, the image list and the path filters from one shared manifest (`scripts/deploy/manifest.json`), take the same step names and flags, and a parity test fails if they diverge.
- **Credentials:** the workflow authenticates to GCP with GitHub OIDC and Workload Identity Federation, so no long-lived key is stored in GitHub. Tenant values and tenant files (`users.yaml`, `blocked.yaml`) are read from Secret Manager at deploy time, and never appear in the repository, the logs or the artifacts. No group map is needed, because membership comes from app roles (CH-0011).
- **One at a time:** one deployment runs at a time. Later merges queue behind it and are not cancelled.
- **Failures:** a failed step stops the sequence. The next deployment starts from the last *successful* deploy, so changes that were never deployed are included.
- **Destructive plans stop:** a plan that destroys or replaces a stateful resource (Cloud SQL, buckets, secrets) stops and waits for a person's approval.
- **Smoke checks:** the MCP server and the app answer; an MCP request without a token gets 401; the active config bundle is the one just published.
- **Record:** each deployment records the commit, the steps it ran, the image tag and the config version, in the workflow summary and in a deploy marker in GCS.
- **Rollback:** a manual run of the workflow can re-activate an earlier config bundle, or redeploy an earlier image tag.

# Notes

Development environment only. Production deployments stay with [NFR-OPS-001](NFR-OPS-001.md). Entra changes stay manual, and so do the first-time steps `state` and `base` and the Workload Identity Federation setup.
