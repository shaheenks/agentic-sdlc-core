# sdlc_auth

Entra ID identity for the platform. Stage 2.

- `sdlc_auth.entra.EntraTokenVerifier` (extra `server`): a fastmcp `JWTVerifier` subclass that
  checks signature (JWKS), exp, the v2 issuer, audience (client ID or `api://<client id>`), the
  `access_as_user` scope, and `tid` + `oid`, and rejects app-only tokens.
- `Principal` / `principal_from_claims`: the user normalized from validated claims
  (oid, tid, upn, name, scopes, app roles from the `roles` claim). A `groups` claim is ignored:
  membership comes from app roles and users.yaml only (CH-0011), so there is no group overage and no
  Graph lookup.
- GCP stack (CH-0021, extra `server`): `sdlc_auth.google.GoogleTokenVerifier` (Google ID tokens: issuer
  `https://accounts.google.com`, our OAuth client IDs, `email_verified`, allowed `hd`; user = `sub`),
  `principal_from_google_claims`, `google_verifier_from_env` (`SDLC_OAUTH_CLIENT_IDS`,
  `SDLC_ALLOWED_DOMAINS`) and `GoogleAdapter`; `sdlc_auth.groups.CloudIdentityGroups` asks the Cloud
  Identity Groups API which configured groups a user is in (`direct` for Free, `transitive` for Premium;
  cached; a failed lookup gives no groups) and `StaticGroups` for tests.
- `sdlc_auth.adk` (agents): `get_user_token(context)` (request-scoped token passthrough),
  `agent_header_provider` (`Authorization: Bearer` + `X-SDLC-Agent-Session` conversation id: one MCP session
  per user token × conversation), `set_conversation_id` (keeps the parent conversation id for nested
  Goldfish reviewer sessions).

Setup: docs/guides/ENTRA_SETUP.md. Tests: tests/auth (tokens minted by tests/support/entra.py).
