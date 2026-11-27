import logging
import os
import re
from pathlib import Path

from sdlc_logging import configure_logging

from code_workspace import NAME
from code_workspace.run import execute_request

# Each mode reads requests only from its own prefix: the system job from the system's runs, the user job from users'.
RELATIVE = {
    "system": re.compile(r"^artifacts/system/runs/[A-Za-z0-9._-]+/workspace-[0-9]+$"),
    "user": re.compile(r"^artifacts/user-runs/[A-Za-z0-9_-]{1,128}/[A-Za-z0-9._-]+/workspace-[0-9]+$"),
}


def main() -> int:
    """One execution: REQUEST_PATH (a folder of the bucket mounted at STORE_MOUNT_PATH, under the mode's prefix)."""
    configure_logging(NAME)
    log = logging.getLogger(NAME)
    relative, mount = os.environ.get("REQUEST_PATH", ""), os.environ.get("STORE_MOUNT_PATH", "")
    pattern = RELATIVE.get(os.environ.get("WORKSPACE_MODE", "system"))
    if not mount or pattern is None or not pattern.match(relative):
        log.error("REQUEST_PATH must be a workspace folder of this job's mode, and STORE_MOUNT_PATH set")
        return 2
    result = execute_request(Path(mount) / relative / "request.json")
    log.info("workspace done", extra={"ok": result["ok"], "pushed": result["pushed"], "steps": len(result["steps"])})
    return 0  # a failing build or test is a result for the agent, not a failed execution


if __name__ == "__main__":
    raise SystemExit(main())
