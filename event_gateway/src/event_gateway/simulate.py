"""Simulated events from sdlc_ui, until the webhooks are set up (FR-TRIG-006, DEC-0016).

Only sdlc_ui may send one, proven like every call it makes for a user (a declared caller of its surface,
DEC-0010), and only for a team that is both in the environment's `simulation.teams` and one of the user's teams.
The user names the subscription and the subject; for a pull request the gateway reads the base and head branches,
the merge and who merged it from the provider, with the machine user's connection, so the event carries facts and
not what the form claims. The event then goes through the same triage, claim and hand-off as a verified webhook.
"""

import asyncio
import hashlib
import re
from collections.abc import Callable, Mapping
from typing import Any

from sdlc_connectors import ConnectorError, Credential, repository
from sdlc_directory import memberships
from sdlc_identity import Identity, IdentitySettings, Rejected, identify

from event_gateway.triage import Event

SIMULATING_SURFACE = "sdlc_ui"  # DEC-0016: the only surface that may send a simulated event
PULL_REQUEST = "pull_request"
ACTION = re.compile(r"^[a-z_]{1,40}$")
REPO = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+$")


class Refused(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status, self.code, self.message = status, code, message


async def simulating_user(headers: Mapping[str, str], config: Mapping[str, Any], tokens, *, env: str, audience: str):
    """The user sdlc_ui sends a simulation for, or `Refused`."""
    try:
        identity: Identity = await identify(
            headers, IdentitySettings.from_config(config), tokens, env=env, audiences=[audience]
        )
    except Rejected as exc:
        raise Refused(401, "unauthorized", exc.reason) from None
    if identity.surface != SIMULATING_SURFACE:
        raise Refused(403, "wrong_surface", "simulated events come from sdlc_ui only")
    return identity


def allowed_teams(config: Mapping[str, Any], email: str) -> list[str]:
    """The teams this user may simulate events for in this environment: declared for simulation, acted for by the
    system identity, and one of the user's teams."""
    system = config.get("system") or {}
    declared = (system.get("simulation") or {}).get("teams") or ()
    mine = memberships(config, email).teams
    return [t for t in declared if t in (system.get("teams") or ()) and t in mine]


def _repositories(config: Mapping[str, Any], team: str, role: str) -> list[str]:
    systems = (config.get("team_systems") or {}).get(team) or {}
    if role == "control_repo":
        control = systems.get("control_repo")
        return [control["repo"]] if control else []
    return [r["repo"] for r in systems.get("repositories") or ()]


def options(config: Mapping[str, Any], email: str) -> dict[str, Any]:
    """What the Events page offers this user: per team, the enabled subscriptions and their repositories."""
    teams = []
    for team in allowed_teams(config, email):
        subs = []
        for sub_id, sub in sorted((config.get("subscriptions") or {}).items()):
            if not sub.get("enabled", True):
                continue
            event = sub.get("event") or {}
            role = (sub.get("filters") or {}).get("repository", "")
            subs.append(
                {
                    "id": sub_id,
                    "agent": sub.get("agent"),
                    "workflow": sub.get("workflow"),
                    "description": sub.get("description", ""),
                    "event": {k: event.get(k) for k in ("provider", "type", "action") if event.get(k)},
                    "subject": PULL_REQUEST if event.get("type") == PULL_REQUEST else "metadata",
                    "repositories": _repositories(config, team, role),
                }
            )
        teams.append({"team": team, "subscriptions": subs})
    return {"enabled": bool(teams), "teams": teams}


def delivery_id(*facts: Any) -> str:
    """`sim-` and a hash of the event's facts: the same event is claimed once (DEC-0016)."""
    return "sim-" + hashlib.sha256("|".join(str(f) for f in facts).encode()).hexdigest()[:32]


async def build_event(
    config: Mapping[str, Any],
    team: str,
    sub: Mapping[str, Any],
    form: Mapping[str, Any],
    token_for: Callable[[str], str | None],
    client=None,
) -> Event:
    """The event a simulation stands for, from the provider's facts for a pull request."""
    wanted = sub.get("event") or {}
    provider_system, event_type = str(wanted.get("provider") or ""), str(wanted.get("type") or "")
    action = str(form.get("action") or wanted.get("action") or "")
    if action and not ACTION.match(action):
        raise Refused(400, "invalid_argument", "action looks like closed or opened")
    repo = str(form.get("repository") or "")
    role = (sub.get("filters") or {}).get("repository", "")
    if role and repo.lower() not in (r.lower() for r in _repositories(config, team, role)):
        raise Refused(400, "invalid_argument", f"choose one of the team's {role.replace('_', ' ')} repositories")
    if event_type != PULL_REQUEST:
        subject = str(form.get("subject") or repo)[:200]
        found = delivery_id(provider_system, event_type, action, repo, subject)
        return Event(provider_system, event_type, found, action, repo, subject=subject)
    if not REPO.match(repo):
        raise Refused(400, "invalid_argument", "name the repository (owner/name)")
    try:
        number = int(form.get("number"))
    except (TypeError, ValueError):
        raise Refused(400, "invalid_argument", "give the pull request's number") from None
    systems = (config.get("team_systems") or {}).get(team) or {}
    entries = [systems.get("control_repo"), *(systems.get("repositories") or ())]
    entry = next((e for e in entries if e and e["repo"].lower() == repo.lower()), None)
    if entry is None:
        raise Refused(400, "invalid_argument", f"{repo} is not one of the team's repositories")
    provider = entry["provider"]
    settings = (config.get("providers") or {}).get(provider) or {}
    if settings.get("system") != provider_system:
        raise Refused(400, "invalid_argument", f"{repo} is not on {provider_system}")
    token = token_for(provider)
    if not token:
        raise Refused(503, "not_connected", f"no system connection for {provider} in this environment")
    account = ((config.get("system") or {}).get("machine_users") or {}).get(provider)
    base_url = entry.get("base_url") or settings.get("base_url") or ""
    credential = Credential(token, account)
    connector = repository(provider_system, settings.get("edition", ""), base_url, entry["repo"], credential, client)
    if not hasattr(connector, "pull_request"):
        raise Refused(400, "not_supported", f"simulated pull request events on {provider_system}: later")
    try:
        facts = await asyncio.to_thread(connector.pull_request, number)
    except ConnectorError as exc:
        status = 404 if exc.code == "not_found" else 502
        raise Refused(status, exc.code, f"{repo}#{number}: {exc.message}") from None
    if action == "closed" and facts.state != "closed":
        raise Refused(409, "not_closed", f"{repo}#{number} is still open: merge or close it first")
    return Event(
        provider=provider_system,
        type=PULL_REQUEST,
        delivery_id=delivery_id(provider_system, repo.lower(), number, action, facts.merge_commit or facts.state),
        action=action,
        repository=entry["repo"],
        merged=facts.merged,
        base_branch=facts.base_branch,
        head_branch=facts.head_branch,
        subject=f"{entry['repo']}#{number}",
        actor=facts.merged_by or "",
    )


def why_not(sub: Mapping[str, Any], event: Event) -> str:
    """A short reason a simulated event matched none of the chosen subscription's filters."""
    filters = sub.get("filters") or {}
    if "merged" in filters and event.merged is not filters["merged"]:
        return f"{event.subject} was {'merged' if event.merged else 'closed without a merge'}"
    for key, value in (("base_branch", event.base_branch), ("head_branch", event.head_branch)):
        pattern = filters.get(key)
        if pattern and not re.search(pattern, value):
            return f"{event.subject}'s {key.replace('_', ' ')} {value!r} does not match {pattern!r}"
    return f"{event.subject} matches no team the system identity acts for"
