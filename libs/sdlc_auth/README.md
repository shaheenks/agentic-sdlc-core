# sdlc_auth

Entra ID identity for the platform. Stage 2.

- `sdlc_auth.entra.EntraTokenVerifier` (extra `server`): a fastmcp `JWTVerifier` subclass that
  checks signature (JWKS), exp, the v2 issuer, audience (client ID or `api://<client id>`), the
  `access_as_user` scope, and `tid` + `oid`, and rejects app-only tokens.
- `Principal` / `principal_from_claims`: the user normalized from validated claims
  (oid, tid, upn, name, group_ids, groups_overage).
- `effective_group_ids` + `GraphGroupResolver`: when a token omits `groups` (overage), look them
  up via Microsoft Graph `transitiveMemberOf` with the server's app credential (10-min cache).
  With no resolver, overage users get no groups (fail closed).
- Stage 2d adds `get_user_token(context)` for agents (token passthrough).

Setup: docs/ENTRA_SETUP.md. Tests: tests/auth (tokens minted by tests/support/entra.py).
