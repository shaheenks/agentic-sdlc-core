## 2026-11-26

* **Create**: [Control Repository](components/control-repository.md) (`libs/sdlc_control`), the control repository's
  rules shared by both MCP servers. Phase 5a milestone 1 built ([DEC-0015](decisions/DEC-0015.md)):
  `subscriptions.yaml`, `env/<env>/system.yaml`, system surfaces, `workspace` on repositories, `system_policy` and
  the system identity's row in the permission diff.
* **Update**: [DEC-0015](decisions/DEC-0015.md) accepted: FR-TRIG-001, FR-TRIG-003, FR-SDLC-006, FR-CONN-004,
  FR-IDN-004 and FR-AGT-004 changed; phase 5 split into 5a and 5b.
* **Create**: [DEC-0015](decisions/DEC-0015.md), proposed: phase 5a, from a merged design to plan and implementation
  pull requests on the feature branches, through a public event gateway, Cloud Tasks, event_agent_mcp with a machine
  user's PAT, and the Code Workspace; 5b holds the review workflows.
* **Update**: [DEC-0014](decisions/DEC-0014.md) accepted and built: private Bitbucket Cloud and Data Center git
  sources, with `credential_scheme` and `credential_username`; FR-KNOW-001 gains a criterion.
* **Create**: [DEC-0014](decisions/DEC-0014.md), proposed: private Bitbucket knowledge sources; a git source may
  declare its token's sign-in scheme and username, with defaults by host.
* **Update**: [DEC-0013](decisions/DEC-0013.md) built: feature branches on the control and target repositories opened
  on the user's approval in chat; Epic, Feature and User Stories (sub-tasks) in Jira, reusing open issues and
  creating a proposed epic only on confirmation; design pull requests into the feature branch and approvals checked
  there. FR-SDLC-001, -002, -003, -005, -006, -013 and FR-HUM-005 changed.
* **Add**: [DEC-0013](decisions/DEC-0013.md), accepted by the user, with their choices: features approved in chat open a
  feature branch on the control and target repositories; Epic → Feature → User Stories (sub-tasks) in Jira, reusing
  open issues and suggesting a missing epic; later pull requests merge into the feature branch and are approved there.
* **Update**: estimates: a feature has a high-level T-shirt size and each story has story points
  ([FR-SDLC-002](requirements/functional/FR-SDLC-002.md) changed); the features skill drafts them, the readiness
  reviewer checks them, and Jira gets a size label and the story points field (found by name or configured).

## 2026-11-25

* **Update**: no publish loop: `publish_feature` retries with an approved feature's control ID (no new pull request),
  a failure after approval returns that ID, and the agent is told never to publish the same feature again. Jira
  issues are not created twice (a feature of the same type and summary is returned instead); the same rule is written
  down for Confluence pages (FR-SDLC-002, FR-SDLC-013).
* **Update**: no duplicate pull requests: before opening one on the control repository, user_agent_mcp lists the open
  ones and returns an open one for the same artifact instead (the workflows wait on it); `control_pull_requests` and
  `repo_pull_requests` list open pull requests, and the agent's instructions and skills check them before any pull
  request is raised. FR-SDLC-013 and FR-SDLC-006 (for ci_workflow_agent's target repositories) changed.
* **Update**: the review ends after one clean round ([FR-SDLC-004](requirements/functional/FR-SDLC-004.md) changed,
  the user's choice), and a drafter reads at most 10 files and lists at most 5 folders per draft
  ([user_agent](components/user-agent.md)): a design run took over 15 minutes.
* **Update**: [sdlc_ui](components/sdlc-ui.md)'s Cloud Run request timeout is 15 minutes for now (the user's choice; 60 minutes briefly): a chat run streams through
  one request, and a design workflow ran past the default five minutes and was cut while drafting.
* **Update**: [sdlc_ui](components/sdlc-ui.md): tool cards summarise each call from its result (what it touched and
  what came of it, errors in plain words, items, previews and links to inspect); a running workflow shows its stage
  (drafting, reviewers done, revising, waiting), sent by the BFF as the agent's state.
* **Update**: [user_agent](components/user-agent.md): the seven reviewers use `gemini-3.5-flash` (`SDLC_REVIEW_MODEL`),
  the chat, drafting and revising keep `gemini-3.8-flash`, both in `eu` (the user's choice: `gemini-3.8-flash` is the
  latest model there, the 3.5 family the faster one).
* **Update**: [Connectors](components/connectors.md): a rejected request names the fields it got wrong (never their
  values). [user_agent_mcp](components/user-agent-mcp.md): a failed Jira creation no longer blocks a retry; a partial
  one is refused with the keys it created.
* **Update**: [user_agent](components/user-agent.md) retries model calls on 429 and 5xx with backoff and runs at
  most three reviewers at once (Gemini answered 503 and failed design runs); [sdlc_ui](components/sdlc-ui.md)
  closes a failed run's open tool cards and says why, uses its own colour tokens (CopilotKit's --muted and
  --accent had made list markers, links and secondary text unreadable), and widens the answer column.
* **Update**: [sdlc_ui](components/sdlc-ui.md): tool calls as concise cards, knowledge queries collapsed with their
  results; elapsed time per answer and per turn.
* **Update**: [GCP Foundation](components/gcp-foundation.md): Cloud NAT on the platform subnet, so user_agent_mcp
  (all egress through the VPC) reaches GitHub, Bitbucket and Atlassian; connection checks failed without it.
* **Update**: connection tokens are checked when saved (a refused token is not stored) and can be tested again
  from the Connections page ([user_agent_mcp](components/user-agent-mcp.md), [sdlc_ui](components/sdlc-ui.md)).
* **Update**: 4a milestones 3 and 4 deployed to development with the first real team; the knowledge refresh added
  its repository. Fixes found on the way: user_agent_mcp declares PyYAML, the user_agent engine reads its packaged
  skills, and the chat takes the page's colours.
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
