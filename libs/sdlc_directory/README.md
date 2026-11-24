# sdlc_directory

A user's teams, team roles and user groups ([Directory](../../spec/components/directory.md); FR-TEAM-001),
from the Google groups the active configuration maps. Group lookups are `static` (a list in the environment's
configuration), `direct` or `transitive` (Cloud Identity Groups API, with the service's credentials). Test from
this folder: `uv run pytest`.
