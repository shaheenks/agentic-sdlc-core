import logging

from sdlc_logging import configure_logging

from code_workspace import NAME


def main() -> int:
    configure_logging(NAME)
    logging.getLogger(NAME).info("code_workspace skeleton: nothing to do yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
