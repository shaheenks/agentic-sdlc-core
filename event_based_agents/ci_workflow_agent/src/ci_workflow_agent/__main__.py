import logging

from sdlc_logging import configure_logging

from ci_workflow_agent import NAME


def main() -> int:
    """ci_workflow_agent runs on Agent Runtime (app.py), started by the event gateway; there is nothing to run here."""
    configure_logging(NAME)
    logging.getLogger(NAME).info("ci_workflow_agent runs on Agent Runtime; deploy it with deploy.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
