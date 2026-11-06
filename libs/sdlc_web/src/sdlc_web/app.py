"""Entry point: ADK's web app (dev UI + API) behind EntraUserBindingMiddleware.

Replaces `adk web` in the agent container. Only reachable through oauth2-proxy, which signs the
user in with Entra and forwards their access token. Identity settings come from env (agents
never read config/): ENTRA_TENANT_ID, ENTRA_API_CLIENT_ID; missing values stop startup.
"""

import logging
import os
from pathlib import Path

import uvicorn
from fastmcp.server.auth import TokenVerifier
from google.adk.cli.fast_api import get_fast_api_app
from sdlc_auth.entra import DEFAULT_AUTHORITY_HOST, EntraTokenVerifier

from sdlc_web.middleware import EntraUserBindingMiddleware
from sdlc_web.retention import sqlite_path, start_retention
from sdlc_web.sessions import SCHEME as AGENT_ENGINE
from sdlc_web.sessions import parse_agent_engine_uri, register_agent_engine_sessions

log = logging.getLogger("sdlc.web")
CHAT_HOME = "/chat/"  # CopilotKit app behind the same oauth2-proxy (ui/copilotkit)


def create_app(
    agents_dir: Path,
    verifier: TokenVerifier,
    host: str,
    port: int,
    session_service_uri: str = "memory://",
    dev_tools: bool = False,
    agui_agent: str | None = None,
    allow_origins: list[str] | None = None,
    trace_to_cloud: bool = False,
    a2a_agent: str | None = None,
    a2a_url: str | None = None,
):
    # Explicit session store: memory:// by default; docker compose persists conversations in
    # sqlite:////data/sessions.db on a volume only this container mounts (agents get no DB
    # credentials). GCP: Agent Engine sessions (agentengine://, sdlc_web.sessions; main() registers
    # the factory that sets the retention TTL).
    adk_app = get_fast_api_app(
        agents_dir=str(agents_dir),
        web=True,
        host=host,
        port=port,
        session_service_uri=session_service_uri,
        artifact_service_uri="memory://",
        use_local_storage=False,
        # The app's public origin(s), when the proxy in front does not forward the browser's Host
        # (Cloud Run: oauth2-proxy sends Host 127.0.0.1:8000). Without it ADK's cross-origin guard
        # refuses the dev UI's module scripts (403). Unset: same-origin only, as before.
        allow_origins=allow_origins or None,
        # GCP (version-02 N4): ADK's Cloud Trace exporter (GOOGLE_CLOUD_PROJECT, the service
        # identity, roles/cloudtrace.agent). Locally: OTLP to Jaeger via OTEL_EXPORTER_OTLP_*.
        trace_to_cloud=trace_to_cloud,
    )

    @adk_app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {"status": "ok"}

    @adk_app.get("/chat", include_in_schema=False)
    async def chat_redirect():
        # oauth2-proxy sends the "/chat/" prefix to the CopilotKit app; a bare /chat lands here
        from fastapi.responses import RedirectResponse

        return RedirectResponse("/chat/", status_code=307)

    agui_path = None
    sessions = None
    public_paths = {"/healthz"}
    if agui_agent or a2a_agent:
        from sdlc_web.agui import session_service

        sessions = session_service(agents_dir, session_service_uri)
    if agui_agent:  # version-01 M5: the CopilotKit web app talks AG-UI to this agent
        from sdlc_web.agui import AGUI_PATH, mount_agui

        mount_agui(adk_app, agents_dir, agui_agent, session_service_uri, sessions=sessions)
        agui_path = AGUI_PATH
    if a2a_agent:  # version-03 P4 C3: the same agent over A2A (JSON-RPC at /a2a)
        from google.adk.cli.utils.agent_loader import AgentLoader

        from sdlc_web.a2a import CARD_PATH, mount_a2a

        agent = AgentLoader(str(agents_dir)).load_agent(a2a_agent)
        mount_a2a(adk_app, agent, a2a_agent, sessions, public_url=a2a_url)
        public_paths.add(CARD_PATH)  # the card describes the agent; calls still need a token
    return EntraUserBindingMiddleware(
        adk_app,
        verifier,
        public_paths=frozenset(public_paths),
        dev_tools=dev_tools,
        agui_path=agui_path,
        # with the chat app on, "/" (and so the landing page after sign-in) is the chat app
        home_path=CHAT_HOME if agui_agent else None,
    )


def verifier_from_env() -> EntraTokenVerifier:
    tenant = os.environ.get("ENTRA_TENANT_ID", "")
    client = os.environ.get("ENTRA_API_CLIENT_ID", "")
    if not tenant or not client:
        raise SystemExit("ENTRA_TENANT_ID and ENTRA_API_CLIENT_ID must be set (fail closed)")
    return EntraTokenVerifier(
        tenant_id=tenant,
        audience=[client, f"api://{client}"],
        required_scopes=[os.environ.get("SDLC_REQUIRED_SCOPE", "access_as_user")],
        # agents never read config/: the (sovereign-cloud) login host comes from the env (E7)
        authority_host=os.environ.get("ENTRA_AUTHORITY_HOST") or DEFAULT_AUTHORITY_HOST,
    )


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(message)s")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    agents_dir = Path(os.environ.get("SDLC_AGENTS_DIR", "agents")).resolve()
    session_uri = os.environ.get("SDLC_SESSION_SERVICE_URI", "memory://")
    days = float(os.environ.get("SDLC_SESSION_RETENTION_DAYS", "7"))
    db_path = sqlite_path(session_uri)
    if db_path is not None:
        start_retention(db_path, days)
        log.info("conversations persisted in %s (retention %s days)", db_path, days)
    elif session_uri.startswith(f"{AGENT_ENGINE}://"):
        parse_agent_engine_uri(session_uri)  # a short or malformed id stops startup
        register_agent_engine_sessions(days)
        log.info("conversations in Agent Engine sessions (retention %s days from start)", days)
    app = create_app(
        agents_dir,
        verifier_from_env(),
        host,
        port,
        session_service_uri=session_uri,
        # Full ADK developer tools (builder, deploy, evals, traces) only when explicitly enabled.
        dev_tools=os.environ.get("SDLC_DEV_TOOLS", "false").lower() == "true",
        # AG-UI endpoint (/agui) for the CopilotKit app; off unless an agent is named
        agui_agent=os.environ.get("SDLC_AGUI_AGENT") or None,
        allow_origins=[
            o.strip() for o in os.environ.get("SDLC_ALLOWED_ORIGINS", "").split(",") if o.strip()
        ],
        trace_to_cloud=os.environ.get("SDLC_TRACE_TO_CLOUD", "").lower() == "true",
        # A2A endpoint (/a2a) for A2A clients; off unless an agent is named. SDLC_A2A_URL is the
        # advertised public /a2a URL (default: the URL the card was requested on).
        a2a_agent=os.environ.get("SDLC_A2A_AGENT") or None,
        a2a_url=os.environ.get("SDLC_A2A_URL") or None,
    )
    log.info("serving agents from %s on %s:%s (Entra user binding on)", agents_dir, host, port)
    uvicorn.run(app, host=host, port=port, proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
