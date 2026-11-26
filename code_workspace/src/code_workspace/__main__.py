import logging
import os
import re
from pathlib import Path

from sdlc_logging import configure_logging

from code_workspace import NAME
from code_workspace.run import execute_request

RELATIVE = re.compile(r"^artifacts/system/runs/[A-Za-z0-9._-]+/workspace-[0-9]+$")


def main() -> int:
    """One execution: REQUEST_PATH (a folder under artifacts/system/runs/ of the bucket mounted at STORE_MOUNT_PATH)."""
    configure_logging(NAME)
    log = logging.getLogger(NAME)
    relative, mount = os.environ.get("REQUEST_PATH", ""), os.environ.get("STORE_MOUNT_PATH", "")
    if not mount or not RELATIVE.match(relative):
        log.error("REQUEST_PATH must be artifacts/system/runs/<run>/workspace-<n> and STORE_MOUNT_PATH set")
        return 2
    result = execute_request(Path(mount) / relative / "request.json")
    log.info("workspace done", extra={"ok": result["ok"], "pushed": result["pushed"], "steps": len(result["steps"])})
    return 0  # a failing build or test is a result for the agent, not a failed execution


if __name__ == "__main__":
    raise SystemExit(main())
