# Change log

## 2026-11-11

- **Update**: the user approved CH-0001, CH-0002, FR-KNOW-006, FR-KNOW-007 and FR-CONN-003 (recorded by Claude on the
  user's instruction).
- **Update**: CH-0001 done. FR-KNOW-006, FR-KNOW-007 and FR-CONN-003 are `built`, satisfied by ingest_loaders,
  sdlc_connectors, ingest_bootstrap, core_mcp and config. FR-KNOW-001, FR-KNOW-004 and FR-CONN-002 lose the split-out
  parts and are back to `draft`. Version-03 P8 names the three requirements as its live-check targets.
- **Update**: CH-0002 done. FR-AUTHZ-001, FR-AUTHZ-002, FR-AUTHZ-005, FR-SURF-002, NFR-REL-001 and NFR-SEC-004 drop
  criteria that NFR-MAINT-002, NFR-MAINT-004, NFR-SEC-002, NFR-SEC-009, FR-CFG-003 and FR-IDN-002 already state, and
  are back to `draft`.
- **Update**: the user re-reviewed and approved the nine requirements edited by CH-0001 and CH-0002: FR-KNOW-001,
  FR-KNOW-004, FR-CONN-002, FR-AUTHZ-001, FR-AUTHZ-002, FR-AUTHZ-005, FR-SURF-002, NFR-REL-001 and NFR-SEC-004 are
  `stable` again (recorded by Claude on the user's instruction).
- **Update**: the user approved CH-0006 (recorded by Claude on the user's instruction). CH-0006 done: offline tests
  `tests/infra/test_compose.py`, `test_workspace.py`, `test_terraform.py` (new dev dependency `python-hcl2`) and
  `tests/agent/test_user_agent.py` now verify compose, workspace, infra_gcp and user_agent. infra_gcp is no longer
  verified by a workflow file.
- **Deprecation**: the user approved CH-0003 (recorded by Claude on the user's instruction). CH-0003 done: `review_code`,
  `generate_tests` and `approve_design` removed from the code, `tools.yaml`, `roles.yaml`, the team files and the
  persona matrix; FR-ACT-001 `deprecated` and `parked`. Policy tests use two fixture-only tools. GCP dev needs
  `-Step images` and `-Step config` together.
- **Update**: the user approved CH-0009 and CH-0011 (recorded by Claude on the user's instruction). CH-0009 done: team
  roles renamed to `member` and `approver` (app roles `SDLC.<Team>.Member|Approver`) and scoped to their team, which
  closes the cross-team leak. The classification ceiling is per source; migration 008 checks each row against its own
  source's ceiling. FR-AUTHZ-006 is `built`. GCP dev needs the Entra app-role switch with `-Step images`, `-Step db`
  and `-Step config` in one window.
- **Update**: CH-0011 done: Entra groups and the group map are gone; membership comes from app roles and users.yaml only.
  FR-IDN-002, FR-AUTHZ-005, FR-CFG-002, FR-IDN-003, NFR-PORT-001, NFR-PRIV-003 and NFR-SEC-004 edited and back to
  `draft`; the seven rule sets edited and back to `draft`. Team `owners` are GitHub handles that CODEOWNERS must
  match. CH-0005 dropped (superseded). Follow-up: remove the unused groups and Graph secrets from infra/gcp.

- **Creation**: NFR-OPS-002 continuous deployment to GCP dev (`draft`) and change record CH-0010: a GitHub workflow (bash on
  Linux runners) deploys every merge to `main`, running only the steps the changes need, in order. `gcp_deploy.ps1`
  stays for Windows next to a new `gcp_deploy.sh`; both read one manifest and a parity test keeps them equal. NFR-MAINT-003
  edited to scope "no secrets" to the `ci` checks; back to `draft`.
- **Creation**: change record CH-0011 (`draft`): membership from app roles only. It drops Entra groups and the group map,
  supersedes CH-0005, and lists seven requirement edits to apply on approval. Team `owners` become the GitHub handles
  that CODEOWNERS lists (design D15).

- **Creation**: change record CH-0008 (`draft`), the workflow platform design baseline, and the target design
  `docs/designs/workflow-platform.md`. Added 15 draft requirements: FR-WFL-001 to FR-WFL-006, FR-IDN-005,
  FR-SURF-004, FR-KNOW-008 to FR-KNOW-010, FR-CONV-002, NFR-REL-005, NFR-SEC-012 and NFR-SEC-013.
- **Update**: FR-AUTHZ-003 (platform and team roles), NFR-SEC-001 (event services, agent gateway) and NFR-QUAL-001
  (eval covers every content type) edited; back to `draft`.
- **Deprecation**: FR-AUTO-001, replaced by the FR-WFL requirements and FR-IDN-005.
- **Update**: system context rewritten around the workflow classes, and conventions gain the `WFL` area; both back to
  `draft`.
- **Update**: design decisions D1 to D7 applied:
  - roles: platform `viewer` and `admin`; team `member` and optional `approver`, scoped to their team (new
    FR-AUTHZ-006);
  - ops findings go to Jira or an admin alert;
  - the coding agent is built on Google ADK;
  - Kubernetes and Splunk push;
  - third-party agents use A2A with the user token (FR-SURF-002 back to `draft`);
  - the Agent Gateway is optional;
  - memory is parked (FR-CONV-002 `parked`).
- **Creation**: change record CH-0009 (`draft`): rename the team roles and fix the cross-team role leak.
- **Update**: design decisions D10 and D11 recorded:
  - MCP backends can be segregated per workflow (new NFR-SEC-014);
  - autonomous workflows use server-side service connections, initially broad-scoped Jira, Confluence and Bitbucket
    tokens (new FR-CONN-004);
  - NFR-SEC-012 now keeps every external credential out of the sandbox (the runtime pushes the patch);
  - NFR-SEC-013 now covers all external-system credentials.
- **Update**: design decisions D8, D9 and D12 recorded:
  - each team's Jira project for ops findings is declared in its team configuration (FR-WFL-005);
  - the role rename switches the Entra app roles in one step (CH-0009);
  - one set of service tokens per workflow (FR-CONN-004).

- **Update**: design decision D13 recorded: admin alerts go to a Jira queue or an email message, declared in
  platform configuration (FR-WFL-005). No design questions are open.

## 2026-11-10

- **Creation**: change records CH-0001 to CH-0007 (`draft`, awaiting review), from a review of the
  requirements and design: built vs live split, one owner per criterion, retire the SDLC action
  stubs, artifact version limit, remove the Graph overage fallback, tests for unverified
  components, checks for the specification tooling. New draft requirements FR-KNOW-006,
  FR-KNOW-007, FR-CONN-003 and NFR-MAINT-005.
- **Creation**: bundle scaffold (OKF 0.2), [conventions](conventions.md) and the
  `scripts/okf_bundle.py` lint and index tool.
- **Creation**: [system context](system/context.md), 36 functional and 32 non-functional
  requirements, drafted from `docs/FEATURE_INVENTORY.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md` and
  `docs/plans/version-03.md`.
- **Update**: all 68 requirements reviewed and accepted; they are now `stable`.
- **Creation**: component register (22 components, accepted as a first version: `stable`) with `satisfies` and
  `verified_by` trace keys, and the generated [traceability matrix](traceability.md).
- **Update**: CI job `knowledge` runs the bundle lint; pull requests get a drift hint.
- **Update**: change records (`changes/CH-<nnnn>.md`) defined in the conventions and checked by the
  lint; working rules added to `CLAUDE.md`. No existing work is backfilled.
- **Creation**: seven rule sets in `rules/`, moved word for word from `CLAUDE.md`, which now keeps
  the always-apply rules and a routing table. Requirement sources point at the rule sets.
- **Update**: system context, conventions and the seven rule sets reviewed and accepted (`stable`).
