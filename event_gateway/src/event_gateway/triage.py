"""Verifying a delivery and matching it to the subscriptions declared in configuration (FR-TRIG-001, DEC-0015).

Only metadata is read: the provider and event type, the repository and which team it belongs to (only the teams the
system identity acts for), whether a pull request was merged, and its base and head branches. The branch filters'
named groups become the run's inputs.
"""

import hashlib
import hmac
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

GITHUB = "github"


def verify_github(secret: bytes | None, body: bytes, signature: str | None) -> bool:
    """`X-Hub-Signature-256`: sha256=<hex HMAC of the raw body with the webhook's secret>, compared in constant time."""
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.removeprefix("sha256="))


@dataclass(frozen=True)
class Event:
    """What the gateway knows about one verified delivery, all metadata."""

    provider: str
    type: str
    delivery_id: str
    action: str = ""
    repository: str = ""
    merged: bool | None = None
    base_branch: str = ""
    head_branch: str = ""
    subject: str = ""
    actor: str = ""  # attribution only; never grants anything (FR-IDN-004)

    def metadata(self) -> dict[str, str]:
        return {
            "event_source": self.provider,
            "event_type": f"{self.type}.{self.action}" if self.action else self.type,
            "delivery_id": self.delivery_id,
            "subject": self.subject,
        }


def github_event(event_type: str, delivery_id: str, payload: Mapping[str, Any]) -> Event:
    repo = str((payload.get("repository") or {}).get("full_name") or "")
    pr = payload.get("pull_request") or {}
    number = pr.get("number")
    return Event(
        provider=GITHUB,
        type=event_type,
        delivery_id=delivery_id,
        action=str(payload.get("action") or ""),
        repository=repo,
        merged=bool(pr.get("merged")) if pr else None,
        base_branch=str((pr.get("base") or {}).get("ref") or ""),
        head_branch=str((pr.get("head") or {}).get("ref") or ""),
        subject=f"{repo}#{number}" if number else repo,
        actor=str((payload.get("sender") or {}).get("login") or ""),
    )


@dataclass(frozen=True)
class Match:
    subscription_id: str
    subscription: Mapping[str, Any]
    team: str
    inputs: Mapping[str, str] = field(default_factory=dict)


def _teams_of(config: Mapping[str, Any], event: Event, role: str) -> list[str]:
    """The system identity's teams whose control repository (or one of whose product repositories) the event is
    from, on the event's provider."""
    found = []
    systems = config.get("team_systems") or {}
    providers = config.get("providers") or {}
    for team in (config.get("system") or {}).get("teams") or ():
        team_systems = systems.get(team) or {}
        entries = [team_systems.get("control_repo")] if role == "control_repo" else team_systems.get("repositories")
        for entry in entries or ():
            if not entry or entry["repo"].lower() != event.repository.lower():
                continue
            if (providers.get(entry["provider"]) or {}).get("system") == event.provider:
                found.append(team)
    return found


def _branch(pattern: str | None, value: str, inputs: dict[str, str]) -> bool:
    if pattern is None:
        return True
    match = re.search(pattern, value)
    if not match:
        return False
    inputs.update({k: v for k, v in match.groupdict().items() if v is not None})
    return True


def matches(config: Mapping[str, Any], event: Event) -> list[Match]:
    """The enabled subscriptions this event starts, each for one team."""
    found = []
    for sub_id, sub in (config.get("subscriptions") or {}).items():
        wanted = sub.get("event") or {}
        if not sub.get("enabled", True) or wanted.get("provider") != event.provider or wanted.get("type") != event.type:
            continue
        if wanted.get("action") and wanted["action"] != event.action:
            continue
        filters = sub.get("filters") or {}
        if "merged" in filters and event.merged is not filters["merged"]:
            continue
        inputs: dict[str, str] = {}
        if not _branch(filters.get("base_branch"), event.base_branch, inputs):
            continue
        if not _branch(filters.get("head_branch"), event.head_branch, inputs):
            continue
        for team in _teams_of(config, event, filters.get("repository", "")):
            found.append(Match(sub_id, sub, team, dict(inputs)))
    return found
