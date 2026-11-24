"""Approximate rate limits on tool calls: sliding one-minute windows, counted per service instance until an
operations database exists (DEC-0003)."""

import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from typing import Any

from sdlc_directory import Memberships

from sdlc_policy.policy import Decision, matches

WINDOW_SECONDS = 60.0


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._calls: dict[tuple[str, str], deque[float]] = {}

    @staticmethod
    def limits(config: Mapping[str, Any], memberships: Memberships) -> tuple[int | None, int | None, str]:
        """(per user per minute, per team per minute, rule). The most generous override that applies wins.
        A limit that is not declared is not enforced."""
        declared = (config.get("rate_limits") or {}).get("tool_calls") or {}
        per_user, rule = declared.get("per_user_per_minute"), "rate_limits.tool_calls"
        for override in declared.get("overrides") or ():
            value = override.get("per_user_per_minute")
            if value is not None and matches(override.get("to") or {}, memberships):
                if per_user is None or value > per_user:
                    per_user, rule = value, f"rate_limits.tool_calls.overrides:{override['id']}"
        return per_user, declared.get("per_team_per_minute"), rule

    def check(self, config: Mapping[str, Any], user_id: str, memberships: Memberships, team: str | None) -> Decision:
        """Count one tool call, or refuse it when a limit is reached."""
        per_user, per_team, rule = self.limits(config, memberships)
        now = self._clock()
        keys = [(("user", user_id), per_user, rule)]
        if team is not None:
            keys.append((("team", team), per_team, "rate_limits.tool_calls.per_team"))
        with self._lock:
            windows = []
            for key, limit, key_rule in keys:
                window = self._calls.setdefault(key, deque())
                while window and window[0] <= now - WINDOW_SECONDS:
                    window.popleft()
                if limit is not None and len(window) >= limit:
                    return Decision(False, key_rule, "rate_limited")
                windows.append(window)
            for window in windows:
                window.append(now)
        return Decision(True, rule)
