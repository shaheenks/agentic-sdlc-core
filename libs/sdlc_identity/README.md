# sdlc_identity

Google account token verification ([Identity](../../spec/components/identity.md); DEC-0001, DEC-0009). ID tokens
are checked against Google's signing keys and access tokens by introspection; verified claims are cached for 300
seconds. `check` then applies the active configuration: declared OAuth client (the surface), `openid` and `email`
scopes, allowed domain, no service accounts, the block list. Test from this folder: `uv run pytest`.
