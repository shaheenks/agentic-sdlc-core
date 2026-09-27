"""Per-user tool call rates (EffectivePolicy.rate_limits), sliding one-minute window.

Checked after authorization, so refused calls do not use up quota. A call is counted only if every
applicable scope ("*" and the tool's own) has room. In memory per process: with several MCP server
instances each enforces its own window (a shared store comes with the GCP operations stage).
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from sdlc_config import EffectivePolicy

from sdlc_policy import Decision

WINDOW_SECONDS = 60.0


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._calls: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, policy: EffectivePolicy, oid: str, tool: str) -> Decision | None:
        """None if the call may proceed (and is counted); otherwise a deny Decision."""
        scopes = [s for s in ("*", tool) if s in policy.rate_limits]
        if not scopes:
            return None
        now = self._clock()
        with self._lock:
            windows = []
            for scope in scopes:
                window = self._calls.setdefault((oid, scope), deque())
                while window and window[0] <= now - WINDOW_SECONDS:
                    window.popleft()
                limit, rule = policy.rate_limits[scope]
                if len(window) >= limit:
                    retry = max(1, math.ceil(window[0] + WINDOW_SECONDS - now))
                    what = "all tools" if scope == "*" else f"'{tool}'"
                    return Decision(
                        False,
                        f"rate limit: {limit} calls per minute for {what}; retry in {retry} s",
                        rule,
                    )
                windows.append(window)
            for window in windows:
                window.append(now)
        return None

    def prune(self) -> None:
        """Drop idle users' windows (memory stays bounded by active users)."""
        cutoff = self._clock() - WINDOW_SECONDS
        with self._lock:
            for key in [k for k, w in self._calls.items() if not w or w[-1] <= cutoff]:
                del self._calls[key]
