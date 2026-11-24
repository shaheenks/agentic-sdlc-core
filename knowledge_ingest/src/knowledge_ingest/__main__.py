import logging

from sdlc_logging import configure_logging

from knowledge_ingest import NAME


def main() -> int:
    configure_logging(NAME)
    logging.getLogger(NAME).info("knowledge_ingest skeleton: nothing to do yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
