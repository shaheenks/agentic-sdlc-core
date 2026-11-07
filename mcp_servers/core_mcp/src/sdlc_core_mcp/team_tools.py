"""The caller's teams for the agent (Stage 4; version-03 P10 G9: which team a document is for).

- `get_agent_context(team=None)`: team instructions and context, plus the caller's `teams`
  (name + one-line description) and `default_team`. With `team`, only that team's instructions
  and context; a team the caller is not in answers "unknown team", like one that doesn't exist.
- `resolve_team(hints)`: matches names from the conversation (repositories, projects, sources)
  against the caller's OWN teams only, so it never discloses another team.

A team is guidance for the agent (content, templates, lenses). It grants nothing: tools,
skills and data still come from the caller's whole policy.
"""

import re

from fastmcp.exceptions import ToolError
from sdlc_config import EffectivePolicy, Snapshot, document_flow

from sdlc_core_mcp.identity import request_identity

MAX_HINTS = 20
MAX_HINT_CHARS = 200
MIN_KEYWORD_CHARS = 3
# no argument values in errors: the audit log records the error text
UNKNOWN_TEAM = "unknown team (not one of your teams)"


def team_keywords(snapshot: Snapshot, policy: EffectivePolicy, team: str) -> dict[str, str]:
    """Names that point to one of the caller's teams: keyword (lower case) -> what it is."""
    definition = snapshot.teams[team]
    words: dict[str, str] = {team: "team name"}
    for key, value in sorted(definition.context.items()):
        value = value.strip().lower()
        words.setdefault(value, f"team context {key}")
        if "/" in value:  # a URL or path: its last part is how people name it
            last = value.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
            words.setdefault(last, f"team context {key}")
    for args in definition.constraints.values():
        for arg, values in sorted(args.items()):
            for value in sorted(values):
                words.setdefault(value.lower(), f"{arg} of the team")
    for source_id in policy.readable_sources:
        if snapshot.sources[source_id].owner_team == team:
            words.setdefault(source_id.lower(), "knowledge source of the team")
    return {w: why for w, why in words.items() if len(w) >= MIN_KEYWORD_CHARS}


def match_teams(snapshot: Snapshot, policy: EffectivePolicy, hints: list[str]) -> dict:
    """One team, `ambiguous` (candidates) or `none`, with reasons. Only the caller's teams."""
    teams = sorted(policy.teams)
    texts = [str(h)[:MAX_HINT_CHARS].lower() for h in hints[:MAX_HINTS]]
    found: dict[str, list[str]] = {}
    for team in teams:
        for word, why in team_keywords(snapshot, policy, team).items():
            pattern = re.compile(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])")
            if any(pattern.search(text) for text in texts):
                found.setdefault(team, []).append(f"{word} mentioned ({why})")

    def describe(team: str) -> dict:
        return {
            "team": team,
            "description": snapshot.teams[team].description,
            "reasons": found.get(team, []),
        }

    result = {"default_team": policy.default_team}
    if len(found) == 1:
        [team] = found
        return result | {"result": "team", "team": team, "reason": "; ".join(found[team])}
    if len(found) > 1:
        return result | {
            "result": "ambiguous",
            "team": None,
            "reason": "the hints point to several of your teams",
            "candidates": [describe(t) for t in sorted(found)],
        }
    if len(teams) == 1:
        return result | {"result": "team", "team": teams[0], "reason": "your only team"}
    if policy.default_team:
        return result | {
            "result": "team",
            "team": policy.default_team,
            "reason": "your default team (no hint matched)",
        }
    return result | {
        "result": "none",
        "team": None,
        "reason": "no hint matched one of your teams" if teams else "you are not in any team",
        "candidates": [describe(t) for t in teams],
    }


def make_team_tools() -> list:
    async def get_agent_context(team: str | None = None) -> dict:
        """Your team instructions and context, your teams (name + description) and default
        team. With `team` (one of your teams): only that team's instructions and context."""
        ident = await request_identity()
        policy, snapshot = ident.policy, ident.snapshot
        if team is not None and team not in policy.teams:
            raise ToolError(UNKNOWN_TEAM)
        instructions = [i for i in policy.agent_instructions if team is None or i.team == team]
        context = {t: dict(v) for t, v in policy.context.items() if team is None or t == team}
        return {
            "team": team,
            "instructions": [
                {"team": item.team, "source": item.source, "text": item.text}
                for item in instructions
            ],
            "context": context,
            "teams": [
                {"name": t, "description": snapshot.teams[t].description}
                for t in sorted(policy.teams)
            ],
            "default_team": policy.default_team,
            # G7: platform defaults, plus the team's own when one is named (the locked team)
            "flows": {"document": document_flow(snapshot, policy, team)},
            "config_version": policy.config_version,
        }

    async def resolve_team(hints: list[str]) -> dict:
        """Which of your teams a piece of work is for, from names in the conversation
        (repositories, projects, services, sources). Answers one team with its reason,
        `ambiguous` with candidates (ask the user), or `none`. Guidance only: grants nothing."""
        ident = await request_identity()
        return match_teams(ident.snapshot, ident.policy, list(hints))

    return [get_agent_context, resolve_team]
