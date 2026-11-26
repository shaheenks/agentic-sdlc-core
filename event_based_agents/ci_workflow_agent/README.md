# ci_workflow_agent

Plans and implements approved designs, one run per event ([component](../../spec/components/ci-workflow-agent.md),
[DEC-0015](../../spec/decisions/DEC-0015.md)). An ADK graph workflow on the event agents' own Agent Runtime
deployment, acting as the system identity and calling tools only through event_agent_mcp.

The event gateway creates the run's session with its team, subscription, run ID, workflow, inputs and event in the
state (`runtime.py` refuses anything else), then sends the event as the message. The run follows the state:

- `plan` (`ci_plan`: a design merged into `feature/<control-id>` on the control repository): for each target
  repository without an approved or open plan, `implementation-plan` drafts `plan-<repo>.md` from the design and the
  code at the feature branch, one fresh-context reviewer (`review-readiness`) reads it, a reviser applies serious
  findings, and `plan_open_pull_request` opens it into the feature branch. A design a person did not merge gets a
  comment instead.
- `implement` (`ci_implement`: a plan merged): `implementation` writes the change with tests and builds it with
  `workspace_run`; when ready, `implementation_open_pull_request` opens it into the target repository's feature
  branch; when blocked, the reason is commented on the plan's pull request.

Every call to event_agent_mcp carries the run (`X-SDLC-Team`, `X-SDLC-Subscription`, `X-SDLC-Run-Id`, the event)
and the runtime's ID token; the server checks approvals and allows only the subscription's writes. Security and
quality reviews of pull requests come in phase 5b.

Build and test from this folder: `uv run pytest`.

| Variable | Default | Meaning |
|---|---|---|
| `SDLC_MCP_URL` | `http://127.0.0.1:8081/mcp` | event_agent_mcp |
| `SDLC_MCP_AUDIENCE` | the URL without `/mcp` | Audience of the runtime's ID token |
| `SDLC_CALLER_AUTH` | `id_token` | `none` only against a local event_agent_mcp |
| `SDLC_AGENT_MODEL`, `SDLC_REVIEW_MODEL` | `gemini-3.8-flash`, `gemini-3.5-flash` | Drafting and reviewing models |
| `SDLC_MODEL_LOCATION` | `eu` | Vertex AI location of the models |
| `SDLC_SKILLS_DIR` | packaged, else the repository's `skills/` | Skills |
