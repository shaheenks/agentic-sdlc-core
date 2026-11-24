import logging

from sdlc_config_store import ConfigUnavailable
from sdlc_logging import configure_logging
from sdlc_service import serve

from user_agent_mcp import DEFAULT_PORT, SERVICE, create_app


def main() -> None:
    configure_logging(SERVICE)
    try:
        app = create_app()
    except ConfigUnavailable as exc:  # no verified bundle: refuse to start (FR-CFG-001, NFR-SEC-002)
        logging.getLogger(SERVICE).critical("no verified configuration bundle; not starting: %s", exc)
        raise SystemExit(1) from exc
    serve(app, SERVICE, DEFAULT_PORT)


if __name__ == "__main__":
    main()
