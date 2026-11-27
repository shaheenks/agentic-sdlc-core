---
type: Component
title: "Code Workspace"
description: "Cloud Run jobs that build and test a change: the system job checks out, applies ci_workflow_agent's changes, runs the repository's commands and pushes the working branch; the credential-free user job only builds an archive user_agent_mcp fetched as the user."
tags: [component, execution, events]
status: draft
x-layer: execution
x-folder: code_workspace/
x-depends-on: [/components/secrets, /components/observability]
x-satisfies: [/requirements/functional/FR-SDLC-006, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-SEC-006, /requirements/non-functional/NFR-OBS-003]
---

# Purpose

Agent Runtime is not a build sandbox. ci_workflow_agent edits code and runs tests through this job instead.

# Responsibilities

- For each execution: check out the repository at the working branch, apply the changes the agent sends, run the
  build and test commands the repository declares, push the working branch, and return the results (exit codes,
  test summary, trimmed logs).
- Push only to the run's working branch; never to a protected branch.
- User mode, the job `code-workspace-user` ([DEC-0016](../decisions/DEC-0016.md)): unpack the repository archive
  user_agent_mcp wrote with the request (fetched with the user's connection), apply the changes, run the declared
  commands and return the results. It holds no token, has no git remote and pushes nothing; it reads requests only
  under `artifacts/user-runs/`. The job's own `WORKSPACE_MODE` picks the mode, never the request.
- Start clean every time: no state is kept between executions.
- Carry the run's event metadata and trace context ([NFR-OBS-003](../requirements/non-functional/NFR-OBS-003.md)).

# Out of scope

- Deciding what to change: [ci_workflow_agent](ci-workflow-agent.md).
- Opening pull requests and comments: [event_agent_mcp](event-agent-mcp.md) and [user_agent_mcp](user-agent-mcp.md).

# Interfaces

- Provides: two Cloud Run jobs from one image: the system job, started only by event_agent_mcp, and the user job,
  started only by user_agent_mcp, each with `REQUEST_PATH` as its only override
  ([Workspace Runner](workspace-runner.md)).
- Consumes: the system repository connection's PAT as an environment variable from Secret Manager.

# Depends on

- [Secrets](secrets.md)
- [Observability](observability.md)

# Owns

- Nothing durable.

# Requirements

- [FR-SDLC-006: Implementation by ci_workflow_agent](../requirements/functional/FR-SDLC-006.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-SEC-006: Least-privilege service identities](../requirements/non-functional/NFR-SEC-006.md)
- [NFR-OBS-003: Event metadata on every trace of an unattended run](../requirements/non-functional/NFR-OBS-003.md)

# Realisation

- Folder `code_workspace/`, self-contained; a Cloud Run job in europe-west3 with its own service account, which may
  be run only by event_agent_mcp's service account and has no other platform permissions.
- Egress limited to the declared Git hosts and package registries; the repository's own build and test commands run
  inside the job, so it holds nothing beyond the PAT it needs.
- Built ([DEC-0015](../decisions/DEC-0015.md), phase 5a milestone 4): one execution per `request.json` under
  `artifacts/system/runs/`; it fetches the implementation branch (else the feature branch), applies the change set
  inside the repository, runs the declared setup, build and test commands, pushes only the `sdlc/` branch and writes
  `result.json`. The token reaches git only as a header through git's environment; the repository's commands run
  without any platform variable. One platform image (git, Python 3.12, Node.js); an image per repository is later.
  Egress is not yet limited to the declared hosts.
