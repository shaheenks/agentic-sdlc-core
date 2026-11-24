"""Which teams and user groups a user is in (Directory component; FR-TEAM-001, FR-TEAM-004, FR-AUTHZ-007).

Google tokens carry no groups. Configuration maps each team role and user group to Google group emails;
`Directory.memberships` asks which of those groups the user is in and turns the answer into team roles and
user groups. Only the groups configuration names are ever looked up.

Group lookups (`identity.directory.mode` in the active configuration):
- `static`: a fixed email-to-groups list in the environment's configuration (`users.yaml`), for local runs.
- `direct`: Cloud Identity Groups API, one membership lookup per configured group (Cloud Identity Free;
  no nested groups).
- `transitive`: Cloud Identity Groups API, one search of the user's groups including nested ones (Premium).

A group whose lookup fails gives nothing for that request; the user's other groups still count, since
groups only add access. Answers are cached per user for `identity.directory.cache_seconds` (default 300).
"""

from sdlc_directory.directory import Directory, Memberships
from sdlc_directory.groups import CloudIdentityGroups, GroupLookup, StaticGroups

__all__ = ["CloudIdentityGroups", "Directory", "GroupLookup", "Memberships", "StaticGroups"]
