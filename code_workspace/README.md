# code_workspace

The Cloud Run job where ci_workflow_agent's changes are applied, built, tested and pushed
([component](../spec/components/code-workspace.md), [DEC-0015](../spec/decisions/DEC-0015.md)). Started only by
event_agent_mcp (`workspace_run`), one execution per request; it keeps nothing.

One execution reads `<STORE_MOUNT_PATH>/<REQUEST_PATH>/request.json`, then:
1. fetches the implementation branch `sdlc/<control-id>/<repo>` if it was pushed before, else the feature branch,
   else the default branch;
2. applies the change set (whole files or deletions, inside the repository, never `.git`) and commits it;
3. runs the repository's declared `setup`, `build` and `test` commands (team configuration, `workspace` on the
   repository entry) in order, stopping at the first failure;
4. pushes the commit to the `sdlc/` branch (no other branch is ever pushed);
5. writes `result.json` next to the request: `ok`, `pushed`, `commit`, and each step's exit code, duration and the
   end of its log.

The machine user's token (`SYSTEM_TOKEN_<PROVIDER>`) reaches git only as an HTTP header through git's environment;
the repository's own commands run with `PATH`, `HOME` and the locale only. A failing build or test is a result for
the agent, not a failed execution.

**User mode** (`WORKSPACE_MODE=user`, the job `code-workspace-user`, [DEC-0016](../spec/decisions/DEC-0016.md)):
started only by user_agent_mcp for a change the user implements in chat. The request folder under
`artifacts/user-runs/<user>/` holds the repository's archive, which user_agent_mcp fetched with the user's
connection. The job unpacks it (no links out, no absolute paths), applies the change set, runs the declared commands
and writes `result.json`. It has no token and no git remote, and pushes nothing: user_agent_mcp commits the change
with the user's connection afterwards.

The image has git, Python 3.12 and Node.js. Build and test from this folder: `uv run pytest` (needs git).

| Variable | Default | Meaning |
|---|---|---|
| `STORE_MOUNT_PATH` | - | Mount point of the artifact bucket |
| `WORKSPACE_MODE` | `system` | `system`, or `user` for the credential-free job (set on the job, never by a request) |
| `REQUEST_PATH` | - | Set per execution: `artifacts/system/runs/<run>/workspace-<n>`, or `artifacts/user-runs/<user>/<run>/workspace-<n>` in user mode |
| `SYSTEM_TOKEN_<PROVIDER>` | - | The machine user's token, for example `SYSTEM_TOKEN_GITHUB` (Secret Manager) |
| `WORKSPACE_TIMEOUT_SECONDS` | `1100` | The execution's limit for all commands |
| `WORKSPACE_GIT_NAME`, `WORKSPACE_GIT_EMAIL` | `ci_workflow_agent` | The commits' author |
| `LOG_LEVEL` | `INFO` | Minimum log level |
