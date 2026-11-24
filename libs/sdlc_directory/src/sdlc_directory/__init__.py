"""Which teams and user groups a user is in (Directory component; FR-TEAM-001, FR-TEAM-004, FR-AUTHZ-007).

Membership is declared per environment in `config/env/<env>/users.yaml`, by email: each user's teams (a
team alone means its `member` role, `team:role` names another role) and user groups. The configuration
compiler checks every name against the declared teams, roles and user groups. No directory service is
asked (DEC-0010); a user who is not listed is in no team and no user group.
"""

from sdlc_directory.directory import Memberships, memberships

__all__ = ["Memberships", "memberships"]
