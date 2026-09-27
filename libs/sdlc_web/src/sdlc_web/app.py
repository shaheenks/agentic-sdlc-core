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

log = logging.getLogger("sdlc.web")


def create_app(
    agents_dir: Path,
    verifier: TokenVerifier,
    host: str,
    port: int,
    session_service_uri: str = "memory://",
    dev_tools: bool = False,
):
    # Explicit session store: memory:// by default; docker compose persists conversations in
    # sqlite:////data/sessions.db on a volume only this container mounts (agents get no DB
    # credentials). GCP: Agent Engine sessions (agentengine://).
    adk_app = get_fast_api_app(
        agents_dir=str(agents_dir),
        web=True,
        host=host,
        port=port,
        session_service_uri=session_service_uri,
        artifact_service_uri="memory://",
        use_local_storage=False,
    )

    @adk_app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {"status": "ok"}

    return EntraUserBindingMiddleware(adk_app, verifier, dev_tools=dev_tools)


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
    db_path = sqlite_path(session_uri)
    if db_path is not None:
        days = float(os.environ.get("SDLC_SESSION_RETENTION_DAYS", "7"))
        start_retention(db_path, days)
        log.info("conversations persisted in %s (retention %s days)", db_path, days)
    app = create_app(
        agents_dir,
        verifier_from_env(),
        host,
        port,
        session_service_uri=session_uri,
        # Full ADK developer tools (builder, deploy, evals, traces) only when explicitly enabled.
        dev_tools=os.environ.get("SDLC_DEV_TOOLS", "false").lower() == "true",
    )
    log.info("serving agents from %s on %s:%s (Entra user binding on)", agents_dir, host, port)
    uvicorn.run(app, host=host, port=port, proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
