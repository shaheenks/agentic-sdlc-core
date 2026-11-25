## 2026-11-25

* **Update**: a team's `control_repo` may have any `org/repo` name (such as `<org>/sdlc-control`), the user's
  choice; no two teams share one.
* **Update**: Jira status gates removed, the user's change: no workflow depends on a Feature's status (In Design,
  In Development); approval on the team's control repository is the only gate. FR-SDLC-002, FR-SDLC-003,
  FR-SDLC-006 and [DEC-0012](decisions/DEC-0012.md) changed; `design_status` and `development_status` leave the
  team configuration.
* **Update**: 4a milestone 4: [sdlc_ui](components/sdlc-ui.md) team chats and workflow questions answered in the
  chat. Built: FR-HUM-001, FR-KNOW-004. `design_path` on product repositories is optional.
* **Update**: [DEC-0012](decisions/DEC-0012.md) accepted by the user; [DEC-0008](decisions/DEC-0008.md) superseded.
  FR-SDLC-001, FR-SDLC-002, FR-SDLC-003, FR-SDLC-005, FR-SDLC-006, FR-SDLC-010, FR-SDLC-012, FR-TRIG-003 and
  FR-HUM-005 changed to the control repository; new [FR-SDLC-013](requirements/functional/FR-SDLC-013.md).
  4a milestone 3: the control repository tools and gated Jira writes in
  [user_agent_mcp](components/user-agent-mcp.md), their [Connectors](components/connectors.md) support, and the
  workflows in [user_agent](components/user-agent.md). Built: FR-SDLC-002, FR-SDLC-003, FR-SDLC-004,
  FR-SDLC-005, FR-SDLC-013.
* **Update**: [Configuration Registry](components/configuration-registry.md): a user group can list `teams`
  (or one team role); their members join the group, for their own runs only (membership, not team grants).
* **Update**: [Configuration Registry](components/configuration-registry.md): teams and sources can be one
  YAML file each, `env/<env>/teams/<id>.yaml` and `env/<env>/sources/<id>.yaml`; the example environment uses
  them.
* **Update**: [Configuration Registry](components/configuration-registry.md): teams, user groups and knowledge
  sources, with what they are given, are environment configuration in `config/env/<env>/`; shared files keep only
  tool groups, surfaces, limits, providers and platform settings. The shared/environment merge is gone. Access is
  unchanged in every environment.
* **Update**: [Configuration Registry](components/configuration-registry.md): `grants.yaml` is gone. Teams (and
  their roles) and user groups list the `tool_groups` and `sources` they are given; `everyone: true` on a tool group
  or source gives it to everyone. The compiled bundle keeps its list of grants, so access is unchanged (the
  permission diff between the old and new layout is empty in every environment). Environment files: teams, user
  groups and sources.
* **Update**: [Configuration Registry](components/configuration-registry.md): team systems move from
  `env/<env>/systems.yaml` into `systems` in `teams.yaml`, with the team's control repository (`control_repo`, an `org/repo` name that
  identifies the team) and lists of Jira projects, Confluence spaces and repositories, each with one default; `teams.yaml`,
  `sources.yaml` and `grants.yaml` may have environment files merged by ID. [DEC-0012](decisions/DEC-0012.md)
  revised with the user: drafts stay the user's own artifacts; sdlc-control gates and records only writes to
  Jira, Confluence and repositories, and only steps that start from published items check it.
* **Add**: [DEC-0012](decisions/DEC-0012.md), proposed: each team's `sdlc-control` repository holds every
  feature, design specification and implementation plan, approved by a merged pull request, before agents write to
  Jira, Confluence or product repositories, and records the results of those writes; with the user's choices.
* **Update**: 4a milestone 2: the [Skill Library](components/skill-library.md)'s stage skills and seven
  fresh-context reviewers in `skills/`, the reviewers adapted from EGM (Apache-2.0).
* **Update**: Phase 4 split into 4a (design flow in sdlc_ui) and 4b (A2A router and Gemini Enterprise), the
  user's choice. 4a milestone 1: [Connectors](components/connectors.md) for Jira, GitHub and Bitbucket in both
  editions, teams' systems per environment in the [Configuration Registry](components/configuration-registry.md),
  and Jira and repository tools in [user_agent_mcp](components/user-agent-mcp.md) with argument constraints.
  FR-AUTHZ-003 built.
* **Update**: Phase 3 deployed to development: [user_agent](components/user-agent.md) on
  [Agent Runtime](components/agent-runtime.md) and [sdlc_ui](components/sdlc-ui.md) behind IAP. The user
  confirmed chat and artifacts in the browser.

## 2026-11-24

* **Update**: Phase 3 code: [user_agent](components/user-agent.md) on [Agent Runtime](components/agent-runtime.md)
  (chat with cited knowledge answers, the session's user forwarded to user_agent_mcp) and
  [sdlc_ui](components/sdlc-ui.md) (IAP-verified user, chats as runtime sessions, CopilotKit with AG-UI,
  artifacts and connections pages). FR-AGT-005 and FR-WFL-009 partly built: Gemini Enterprise, workflows and
  waiting runs come later.
* **Update**: Phase 2 deployed to development: the knowledge refresh as one Cloud Build run
  ([Ingest Pipeline](components/ingest-pipeline.md)), [Knowledge Search](components/knowledge-search.md) with
  internal ingress, [user_agent_mcp](components/user-agent-mcp.md) with VPC egress. NFR-ARCH-004 built.
* **Add**: [DEC-0011](decisions/DEC-0011.md), accepted by the user, with their choices: git and folder sources,
  access by source ID without a classification ceiling yet, structural and Gemini-extracted graph,
  `gemini-embedding-001`. Phase 2 code: [Ingest Pipeline](components/ingest-pipeline.md),
  [Knowledge Store](components/knowledge-store.md) (library `sdlc_knowledge`),
  [Knowledge Search](components/knowledge-search.md), knowledge tools and run teams in
  [user_agent_mcp](components/user-agent-mcp.md), sources in [Access Policy](components/access-policy.md) and
  [Configuration Registry](components/configuration-registry.md). Built: FR-KNOW-001, FR-KNOW-002, FR-KNOW-003.
  Partly built and still planned: FR-AUTHZ-004 (no ceiling), FR-KNOW-004 (the confirmation comes with workflow
  runs).
* **Update**: [FR-CFG-002](requirements/functional/FR-CFG-002.md) built: `sdlc-config diff` in the
  [Configuration Registry](components/configuration-registry.md), computed with the Access Policy and shown by CI.
* **Update**: [user_agent_mcp](components/user-agent-mcp.md) deployed to development: one Cloud Storage volume per
  allowed prefix, IAM conditions also naming the prefixes as folders, ingress `all` until sdlc_ui runs there.
* **Add**: [DEC-0010](decisions/DEC-0010.md), accepted by the user: for now sdlc_ui forwards the user from the verified IAP
  assertion and user_agent_mcp trusts only declared callers' service accounts; membership is declared in
  `users.yaml`, not read from Cloud Identity groups. [FR-TEAM-001](requirements/functional/FR-TEAM-001.md)
  rewritten for configured membership; notes on FR-IDN-002 and FR-SURF-003. [Identity](components/identity.md),
  [Directory](components/directory.md), [user_agent_mcp](components/user-agent-mcp.md),
  [sdlc_ui](components/sdlc-ui.md), [Agent Runtime](components/agent-runtime.md) and
  [Configuration Registry](components/configuration-registry.md) updated to match.
* **Update**: Phase 1 code. Realisation of [Identity](components/identity.md),
  [Access Policy](components/access-policy.md), [Directory](components/directory.md),
  [Configuration Registry](components/configuration-registry.md), [user_agent_mcp](components/user-agent-mcp.md)
  and [Artifact Store](components/artifact-store.md) brought to what was built; the three libraries got their
  folders. Built: FR-IDN-001, FR-AUTHZ-001, FR-AUTHZ-006, FR-CFG-001, FR-CFG-003, FR-ART-002, NFR-SEC-002,
  NFR-AUD-002. Partly built and still planned: FR-IDN-002, FR-IDN-003, FR-AUTHZ-002, FR-AUTHZ-003 (no argument
  constraints yet), FR-AUTHZ-005, FR-AUTHZ-007, FR-AUTHZ-008, FR-CFG-004, FR-CFG-005, FR-ART-001, FR-CONN-001,
  FR-CONN-005, FR-MDL-002, FR-TEAM-001, NFR-AUD-001.

## 2026-11-22

* **Create**: Initial specification on OKF 0.3: [conventions](conventions.md), the [component catalogue](components/index.md) (28 components in 7 layers), [requirements](requirements/index.md) (109 functional and non-functional), decisions [DEC-0001](decisions/DEC-0001.md) to [DEC-0009](decisions/DEC-0009.md), the generated [traceability](traceability.md) matrix, and a MkDocs site built from `spec/`.
