# Entra ID setup (Stage 2, kept current)

This guide registers the apps, app roles and test users that the MCP server's identity checks
need. Run it once per environment (tenant). You need **Application Administrator** (or
Cloud Application Administrator). A **Global Administrator** or **Privileged Role Administrator** is
needed for admin consent.

Membership comes **only from Entra app roles** (the token's `roles` claim) and the optional, git-ignored
`config/env/<env>/users.yaml`. Entra groups are not used (CH-0011): no group map, no `groups` claim.

> **Windows (cmd / PowerShell): use the script instead of the bash commands below.**
> On Windows `az` is `az.cmd`, so cmd.exe re-parses every argument and breaks inline JSON
> bodies and filters containing `(` `)`. [`scripts/entra_setup.ps1`](../../scripts/entra_setup.ps1)
> does steps 1–3 idempotently, passes JSON via temp files, and has `-DryRun`:
> ```powershell
> az login --tenant <tenant> --allow-no-subscriptions
> .\scripts\entra_setup.ps1 -TestUserA <upn> -TestUserB <upn> -DryRun           # preview
> .\scripts\entra_setup.ps1 -TestUserA <upn> -TestUserB <upn> -WriteLocalFiles  # apply
> ```
> If script execution is blocked: `powershell -ExecutionPolicy Bypass -File .\scripts\entra_setup.ps1 ...`

The commands below use the Azure CLI from **Git Bash** (bash syntax). Portal equivalents are noted where useful.

## 0. Sign in

```bash
az login --tenant <tenant-id-or-domain> --allow-no-subscriptions
az account show --query "{tenant:tenantId, user:user.name}" -o table
```

- **`--allow-no-subscriptions`** is required when the tenant has no Azure subscription, for
  example an Entra-only tenant created from a personal Microsoft account. Without it,
  `az login` fails with "No subscriptions found". All commands here are tenant-level (Graph),
  so no subscription is needed.
- **Admin steps (1–4):** sign in as a tenant admin. For a tenant created from a personal
  Microsoft account, that is the personal account (shown in the tenant as a `…#EXT#…` user;
  it is Global Administrator).
- **Test users:** users you create in the tenant (`user@<tenant>.onmicrosoft.com`) are used
  only in step 5 (`whoami`). They don't need admin roles.

App roles are assigned to users, which works on every tier (Free included).

## What gets created

| Object | Purpose |
|---|---|
| App `sdlc-mcp` (API) | The resource. Tokens for it carry `aud=<sdlc-mcp client id>`, `scp=access_as_user` and the user's app roles in `roles` (§2). The MCP server validates these. |
| App `sdlc-client` (web) | Signs users in for adk web via oauth2-proxy (Stage 2d) and requests `sdlc-mcp/access_as_user`. Redirect URIs: `http://localhost:4180/oauth2/callback`, `https://app-sdlc-dev.shaheenks.co.in/oauth2/callback` (tunnel) and the GCP staging callback (see GCP_DEPLOYMENT.md). |
| App roles on `sdlc-mcp` | `SDLC.User`, `SDLC.Admin`, `SDLC.<Team>.Member` / `.Approver` (§2). Config grants them as `app_role: <value>`. |
| Test users | A payments member, a platform member, an admin and (optionally) a payments approver: different app roles → different `whoami`. UPNs are passed on the command line, never stored in the repo. |

## 1. API app: `sdlc-mcp`

```bash
TENANT_ID=$(az account show --query tenantId -o tsv)
API_APP_ID=$(az ad app create --display-name sdlc-mcp --sign-in-audience AzureADMyOrg \
  --query appId -o tsv)
az ad app update --id $API_APP_ID --identifier-uris api://$API_APP_ID
API_OBJ_ID=$(az ad app show --id $API_APP_ID --query id -o tsv)
SCOPE_ID=$(python -c "import uuid; print(uuid.uuid4())")
AZ_CLI_CLIENT=04b07795-8ddb-461a-bbee-02f9e1bf7b46   # Azure CLI, pre-authorized for dev testing

az rest --method PATCH --url "https://graph.microsoft.com/v1.0/applications/$API_OBJ_ID" \
  --headers "Content-Type=application/json" --body "{
  \"api\": {
    \"requestedAccessTokenVersion\": 2,
    \"oauth2PermissionScopes\": [{
      \"id\": \"$SCOPE_ID\", \"value\": \"access_as_user\", \"type\": \"User\", \"isEnabled\": true,
      \"adminConsentDisplayName\": \"Use SDLC tools as the signed-in user\",
      \"adminConsentDescription\": \"Lets the app call the SDLC MCP server on behalf of the signed-in user.\",
      \"userConsentDisplayName\": \"Use SDLC tools as you\",
      \"userConsentDescription\": \"Lets the app call the SDLC MCP server on your behalf.\"
    }],
    \"preAuthorizedApplications\": [{\"appId\": \"$AZ_CLI_CLIENT\", \"delegatedPermissionIds\": [\"$SCOPE_ID\"]}]
  },
  \"groupMembershipClaims\": \"None\",
  \"optionalClaims\": {\"accessToken\": []}
}"

# Enterprise app (service principal). Only assigned users can get tokens for it.
API_SP_ID=$(az ad sp create --id $API_APP_ID --query id -o tsv)
az ad sp update --id $API_SP_ID --set appRoleAssignmentRequired=true
echo "ENTRA_TENANT_ID=$TENANT_ID"; echo "ENTRA_API_CLIENT_ID=$API_APP_ID"
```

Notes:
- **`requestedAccessTokenVersion: 2`** is required. The server only trusts the v2 issuer
  `https://login.microsoftonline.com/<tenant>/v2.0` (host from `platform.yaml` `identity.authority_host`;
  sovereign clouds use their own), and v2 tokens carry the client ID as `aud`.
- **Identifier URI `api://<client id>`**: Entra's default app policy rejects custom URIs such as
  `api://sdlc-mcp` unless they use a verified domain. `config/platform.yaml` expects
  `api://${ENTRA_API_CLIENT_ID}`, so no config change is needed per tenant.
- **`groupMembershipClaims: None`**: tokens carry no `groups` claim. The server would ignore it anyway
  (membership comes from app roles only), and without it tokens stay small.
- **Azure CLI pre-authorization** is a dev convenience: it lets you test with
  `az account get-access-token` before the web sign-in (2d) exists. Remove it in prod.

## 2. App roles and test users

App roles are defined on `sdlc-mcp`, assigned to users on its enterprise app, and arrive in the access
token's **`roles`** claim. Role values are not secrets; config grants them as `app_role: <value>`.

| App role | Grants | Config |
|---|---|---|
| `SDLC.User` | viewer (platform role) | `roles.yaml` binding |
| `SDLC.Admin` | admin (platform role) | `roles.yaml` binding |
| `SDLC.Payments.Member` / `SDLC.Payments.Approver` | payments member / approver (team roles) | `teams/payments.yaml` membership |
| `SDLC.Platform.Member` / `SDLC.Platform.Approver` | sdlc-platform member / approver | `teams/sdlc-platform.yaml` membership |
| `SDLC.Webapp.Member` / `SDLC.Webapp.Approver` | webapp member / approver | `teams/webapp.yaml` membership |

The script defines all of them (`$AppRoles`; `tests/policy/test_app_roles.py` checks that the list matches
config) and assigns them: test user A gets `SDLC.User` + `SDLC.Payments.Member`, user B `SDLC.User` +
`SDLC.Platform.Member`, `-AdminUser` `SDLC.User` + `SDLC.Admin`, and `-AppRoleUser` the roles in
`-AppRoleUserRoles`:

```powershell
# tenant change: admin account, confirmed first. -DryRun shows the plan.
.\scripts\entra_setup.ps1 -TestUserA <upn> -TestUserB <upn> -AdminUser <upn> -DryRun
```

Notes:
- An app-role assignment also satisfies `appRoleAssignmentRequired`: an assigned user can get tokens.
- New or removed roles show up at the user's **next token** (sign out and in, or wait for the refresh).
- Removing a role: unassign it in the portal (Enterprise applications > sdlc-mcp > Users and groups). To
  delete a role definition, disable it on the app first (the script only adds or updates).
- Check: `whoami(explain=true)` lists `app_roles` and the teams / roles they matched;
  `uv run sdlc-config explain --app-roles SDLC.User,SDLC.Payments.Member` shows the same offline.

## 3. Client app: `sdlc-client` (needed for Stage 2d, web sign-in)

```bash
CLIENT_APP_ID=$(az ad app create --display-name sdlc-client --sign-in-audience AzureADMyOrg \
  --web-redirect-uris http://localhost:4180/oauth2/callback --query appId -o tsv)
az ad app permission add --id $CLIENT_APP_ID --api $API_APP_ID --api-permissions $SCOPE_ID=Scope
az ad sp create --id $CLIENT_APP_ID
az ad app permission admin-consent --id $CLIENT_APP_ID
CLIENT_SECRET=$(az ad app credential reset --id $CLIENT_APP_ID --display-name oauth2-proxy \
  --years 1 --query password -o tsv)
echo "ENTRA_CLIENT_ID=$CLIENT_APP_ID"; echo "ENTRA_CLIENT_SECRET=$CLIENT_SECRET"   # -> .env only
```

More redirect URIs (tunnel, GCP staging): `.\scripts\entra_setup.ps1 … -RedirectUri <uri>,<uri>` adds the
missing ones and keeps existing ones (`-DryRun` first). Afterwards check each entry separately with
`az ad app show --id <client id> --query web.redirectUris -o json`. This is a tenant change: use the admin
account only with explicit confirmation.

## 4. Moving a tenant from groups to app roles (CH-0009, CH-0011)

Before CH-0009 and CH-0011, membership also came from Entra groups, and the team roles were `developer` and
`lead`. Switch an existing tenant in one window, as the admin account, with each step confirmed:

1. Run `entra_setup.ps1` (`-DryRun` first). It adds the new app roles (`SDLC.<Team>.Member` / `.Approver`),
   assigns them to the test users, and turns the `groups` claim off on `sdlc-mcp`.
2. Give every other user the app roles that match their groups (portal: Enterprise applications > sdlc-mcp >
   Users and groups), or list them in `users.yaml`.
3. Publish the new config (`gcp_deploy.ps1 -Step config` on GCP). Users get their access back on their next
   token.
4. Then, by hand: unassign and disable the old app roles (`SDLC.<Team>.Developer` / `.Lead`), remove the
   `GroupMember.Read.All` permission and the `graph-groups` secret from `sdlc-mcp`, remove the group
   assignments, and delete the `sdlc-*` groups.

## 5. Fill `.env` and verify

```dotenv
ENTRA_TENANT_ID=<tenant id>
ENTRA_API_CLIENT_ID=<sdlc-mcp client id>
ENTRA_CLIENT_ID=<sdlc-client client id>          # Stage 2d
ENTRA_CLIENT_SECRET=<sdlc-client secret>          # Stage 2d
```

```bash
uv run --env-file .env sdlc-config validate --env local
docker compose up -d --build --wait core-mcp

# Stage 2 check, before 2d: sign in as each test user and compare whoami.
az login --tenant $TENANT_ID --allow-no-subscriptions            # as user A
uv run python scripts/mcp_whoami.py --token "$(az account get-access-token \
  --scope api://$API_APP_ID/access_as_user --query accessToken -o tsv)"
# repeat as user B: app roles and teams must differ; a request with no/invalid token gets 401
```

### Stage 2d: sign in through the web UI

```powershell
docker compose up -d --build --wait     # needs ENTRA_CLIENT_ID/SECRET and OAUTH2_PROXY_COOKIE_SECRET in .env
start http://localhost:4180             # sign in as a test user, then use the "user_agent" agent
```

The agent's MCP calls now carry that user's token. `docker compose logs core-mcp` shows
`sdlc.audit` lines with the user's `oid`. The automated end-to-end check needs a real user token:

```powershell
$env:AZURE_CONFIG_DIR = "$env:TEMP\az-paul"      # separate CLI profile keeps your admin session
az login --tenant <tenant> --allow-no-subscriptions
$env:SDLC_E2E_USER_TOKEN = az account get-access-token --scope api://<ENTRA_API_CLIENT_ID>/access_as_user --query accessToken -o tsv
uv run --env-file .env pytest tests/e2e/test_stage2_agent.py -v
Remove-Item Env:AZURE_CONFIG_DIR, Env:SDLC_E2E_USER_TOKEN
```

### MCP clients (Antigravity, development)

Antigravity connects straight to `https://mcp-sdlc-dev.shaheenks.co.in/mcp`. In development it uses a user
token from the Azure CLI (works because of the dev-only pre-authorization above):

```powershell
az account get-access-token --scope api://<ENTRA_API_CLIENT_ID>/access_as_user --query accessToken -o tsv
```

The token expires after 60–90 minutes and must be pasted again. Verified: the same user gets the same
policy as in adk web (plan H5). The enterprise path is Antigravity's own OAuth sign-in against Entra
(discovered from the server's `/.well-known/oauth-protected-resource`) with a pre-registered public client
and a loopback redirect URI (an admin change; not set up yet).

For prod or enterprise tenants, remove the Azure CLI pre-authorization:
`.\scripts\entra_setup.ps1 ... -NoAzCliPreAuth` (plan gap E6).

Troubleshooting:
- **401 with a real token:** decode it at https://jwt.ms and check that `iss` ends in `/v2.0`,
  `aud` is the `sdlc-mcp` client ID, `scp` contains `access_as_user`, and `tid` matches.
- **`roles` missing or empty:** check that the user has an app-role assignment on the `sdlc-mcp`
  enterprise app (not only the default access). Sign out and in again to get a fresh token.
- **AADSTS65001 (consent):** run admin consent for `sdlc-client`, or re-check `preAuthorizedApplications`.

## 6. Network egress (E8)

Outbound HTTPS each component needs (the login host comes from `platform.yaml`
`identity.authority_host`; the commercial cloud is shown):

| Component | Destination | Why |
|---|---|---|
| MCP server | `login.microsoftonline.com` (`/<tenant>/discovery/v2.0/keys`) | JWKS: token signature keys (cached 1 h, re-fetched on an unknown `kid`) |
| Agent web app | `login.microsoftonline.com` (JWKS) | Re-validates the forwarded user token |
| oauth2-proxy | `login.microsoftonline.com` (OIDC discovery, authorize redirect, token endpoint) | User sign-in |
| MCP server, agent, ingest | Vertex AI (`aiplatform.googleapis.com`) or the Gemini API | Model calls and embeddings |

Behind a corporate proxy, set the standard variables on each service: `HTTPS_PROXY` (and
`HTTP_PROXY`), plus `NO_PROXY` for internal names (for example `postgres,core-mcp,localhost`).
Token validation honours them (verified by `tests/auth/test_egress_proxy.py`: keys are fetched through
the proxy; without a route the token is rejected, never accepted). If JWKS cannot be reached, every
request is refused (fail closed); the audit reason is `invalid_token`.

## 7. Blocking a user immediately (E3)

Disabling a user in Entra does not end access tokens that were already issued (60-90 minutes). To
cut access on the next request:

1. Copy `config/env/<env>/blocked.yaml.example` to `blocked.yaml` (git-ignored: object IDs are tenant
   data) and add the user's object ID with a reason (ticket, date).
2. The MCP server applies it on the next config reload (file watch locally; bundle pointer later), no
   restart. Every MCP request from that user is refused with 401 and audited as `auth_failure` with
   reason `blocked`, even with a valid token. The web UI may still open, but every tool call fails.
3. Also disable the account in Entra (and revoke its sessions) so no new tokens are issued; remove the
   entry once the account is disabled and old tokens have expired.

Also add `blocked.yaml` to any environment that needs it (on GCP it travels in the config bundle).
