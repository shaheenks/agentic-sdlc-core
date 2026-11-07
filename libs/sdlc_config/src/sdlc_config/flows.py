"""Document flow defaults for one caller (version-03 P10 G7).

Precedence: platform defaults (`platform.yaml` flows.document) -> the team locked for the
document (`addons.flows.document`; only with a team: no team = platform defaults) -> what the
user asks for in the chat (applied by the agent's flow, e.g. `goldfish_review(lenses=...)`).
Caps (`max_lenses`, `max_llm_calls_per_reviewer`, `max_rereviews`) are the lowest of platform
and team. Only skills the caller can see are returned, so a default never names a hidden skill.
Defaults are guidance and limits for the agent's flow; they grant nothing.
"""

from sdlc_config.loader import FLOW_CAPS
from sdlc_config.model import Snapshot
from sdlc_config.resolver import EffectivePolicy


def document_flow(snapshot: Snapshot, policy: EffectivePolicy, team: str | None) -> dict:
    """The effective document flow for `policy`, with `team` (one of its teams) or none."""
    base = snapshot.platform.document_flow

    def visible(names) -> list[str]:
        return [n for n in names if n in policy.skills]

    flow: dict = {
        "team": team,
        "lenses": visible(base.get("lenses", ())),
        **{cap: base.get(cap) for cap in FLOW_CAPS},
        "types": {},
    }
    if team is None or team not in policy.teams:
        return flow | {"team": None}
    own = snapshot.teams[team].document_flow
    if own.get("lenses"):
        flow["lenses"] = visible(own["lenses"])
    for cap in FLOW_CAPS:
        if cap in own:
            flow[cap] = own[cap] if flow[cap] is None else min(flow[cap], own[cap])
    for doc_type, entry in sorted(own.get("types", {}).items()):
        item: dict = {}
        for field in ("template", "brief"):
            if entry.get(field) in policy.skills:
                item[field] = entry[field]
        for field in ("lenses", "required_lenses"):
            if field in entry:
                item[field] = visible(entry[field])
        flow["types"][doc_type] = item
    return flow
