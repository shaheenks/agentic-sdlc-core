"""AG-UI endpoint for the CopilotKit web app (version-01 M5), mounted on the same app as adk web.

`/agui` serves one agent (SDLC_AGUI_AGENT, a folder under the agents dir) over the AG-UI protocol
with `ag_ui_adk`. It sits behind EntraUserBindingMiddleware like every other route, so:
- the user id is always the validated token's `oid` (`user_id_extractor`); ADK sessions are keyed by
  (thread, user), so a thread id from another user never reaches their session, and the
  experimental POST /agents/state answers only for the caller;
- the user's token stays in the request ContextVar (`sdlc_auth.adk`), which the agent's run task
  inherits, so MCP calls carry the user; the token is never put in state or headers-in-state
  (`extract_headers` is not used);
- client state is sanitised by the middleware (no token, `temp:`, `app:` or `user:` keys) and
  `allow_scoped_state_keys` stays off;
- conversations use the configured session store (SDLC_SESSION_SERVICE_URI) and its retention;
  no memory service, nothing saved to memory, sessions are not deleted by ag_ui_adk's cleanup
  (the retention job owns that).
"""

from pathlib import Path

from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from fastapi import FastAPI
from google.adk.cli.utils.agent_loader import AgentLoader
from google.adk.cli.utils.service_factory import create_session_service_from_options

from sdlc_web.middleware import current_oid

AGUI_PATH = "/agui"


def mount_agui(
    app: FastAPI,
    agents_dir: Path,
    agent_name: str,
    session_service_uri: str,
    path: str = AGUI_PATH,
) -> ADKAgent:
    root_agent = AgentLoader(str(agents_dir)).load_agent(agent_name)
    sessions = create_session_service_from_options(
        base_dir=agents_dir, session_service_uri=session_service_uri, use_local_storage=False
    )
    agent = ADKAgent(
        adk_agent=root_agent,
        app_name=agent_name,  # same app name as adk web, so both see the same store layout
        user_id_extractor=lambda _input: current_oid(),
        session_service=sessions,
        use_in_memory_services=False,
        memory_service=None,
        save_session_to_memory_on_cleanup=False,
        delete_session_on_cleanup=False,
        allow_scoped_state_keys=False,
    )
    add_adk_fastapi_endpoint(app, agent, path=path)
    return agent
