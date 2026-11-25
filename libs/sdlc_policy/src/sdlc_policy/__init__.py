"""The Access Policy: who may use which tools, decided from configuration, deny by default.

- A grant makes tool groups available to everyone, to teams (`payments`, or one role: `payments:lead`) or to
  user groups (FR-AUTHZ-007). A tool group no grant names is available to no one. The compiler builds the grants
  from `everyone: true` on tool groups and sources and from what teams, team roles and user groups are given.
- A surface uses only the tool groups declared for it (FR-AUTHZ-006); a tool is allowed when both the user
  and the surface may use it.
- A team run gets what the starter may use and the team (or everyone) is granted (FR-TEAM-002).
- Each decision names the rule that matched (FR-AUTHZ-003).
- Tool calls are rate limited per user and team, counted per service instance (FR-AUTHZ-005, FR-MDL-002).

No code here names a role, team, group or tool: all of them come from the configuration (FR-AUTHZ-001).
"""

from sdlc_policy.policy import DEFAULT_DENY, Decision, EffectivePolicy, NotATeamMember, effective_policy
from sdlc_policy.ratelimit import RateLimiter

__all__ = ["DEFAULT_DENY", "Decision", "EffectivePolicy", "NotATeamMember", "RateLimiter", "effective_policy"]
