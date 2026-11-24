# sdlc_identity

Who the user of a request is ([Identity](../../spec/components/identity.md); DEC-0010, DEC-0001, DEC-0009).
`identify` follows `identity.mode` in the active configuration: `caller_token` (the user forwarded in
`X-SDLC-User-Id` and `X-SDLC-User-Email` by a declared service account, proven by its Google ID token),
`trusted_header` (the same without proof, local environment only) or `oauth` (the user's own Google token,
off for now). Every mode then requires an allowed domain, no service account and no block. Google tokens are
verified against Google's signing keys or by introspection and cached for 300 seconds. Test from this folder:
`uv run pytest`.