# Entra ID setup (Stage 2)

This guide registers the apps, groups and test users that the MCP server's identity checks
need. Run it once per environment (tenant). You need **Application Administrator** (or
Cloud Application Administrator) plus rights to create groups. A **Global Administrator** or
**Privileged Role Administrator** is needed for admin consent.

Commands use the Azure CLI (`az login --tenant <tenant>`) from Git Bash. Portal equivalents are
noted where useful.

## What gets created

| Object | Purpose |
|---|---|
| App `sdlc-mcp` (API) | The resource. Tokens for it carry `aud=<sdlc-mcp client id>`, `scp=access_as_user`, `groups`. The MCP server validates these. |
| App `sdlc-client` (web) | Signs users in for adk web via oauth2-proxy (Stage 2d) and requests `sdlc-mcp/access_as_user`. |
| Security groups | `sdlc-eng-all`, `sdlc-payments-devs`, `sdlc-platform-devs` (+ leads/admins later). Mapped to aliases in `config/env/<env>/groups.yaml`. |
| 2+ test users | For the Stage 2 check: different groups → different `whoami`. |

## 1. API app: `sdlc-mcp`

```bash
TENANT_ID=$(az account show --query tenantId -o tsv)
API_APP_ID=$(az ad app create --display-name sdlc-mcp --sign-in-audience AzureADMyOrg \
  --identifier-uris api://sdlc-mcp --query appId -o tsv)
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
  \"groupMembershipClaims\": \"ApplicationGroup\",
  \"optionalClaims\": {\"accessToken\": [{\"name\": \"groups\"}]}
}"

# Enterprise app (service principal). Only assigned users/groups can get tokens for it.
API_SP_ID=$(az ad sp create --id $API_APP_ID --query id -o tsv)
az ad sp update --id $API_SP_ID --set appRoleAssignmentRequired=true
echo "ENTRA_TENANT_ID=$TENANT_ID"; echo "ENTRA_API_CLIENT_ID=$API_APP_ID"
```

Notes:
- **`requestedAccessTokenVersion: 2`** is required. The server only trusts the v2 issuer
  `https://login.microsoftonline.com/<tenant>/v2.0`, and v2 tokens carry the client ID as `aud`.
- **`api://sdlc-mcp`**: if a tenant policy rejects this identifier URI, use `api://$API_APP_ID`
  instead and change the second `audience` entry in `config/platform.yaml` to match.
- **`groupMembershipClaims: ApplicationGroup`** puts only groups *assigned to this app* in the
  token. That keeps tokens small and avoids group overage. Assigning groups to an enterprise app
  requires **Entra ID P1/P2**. Without P1, use `"SecurityGroup"` instead (all of the user's
  security groups) and configure the Graph fallback in step 4 for users with more than 200 groups.
- **Azure CLI pre-authorization** is a dev convenience: it lets you test with
  `az account get-access-token` before the web sign-in (2d) exists. Remove it in prod.

## 2. Groups and test users

```bash
for g in sdlc-eng-all sdlc-payments-devs sdlc-platform-devs; do
  az ad group create --display-name $g --mail-nickname $g --query "{name:displayName,id:id}" -o tsv
done

# Assign each group to the API app (default access role = all-zero GUID). Needs P1/P2.
for g in sdlc-eng-all sdlc-payments-devs sdlc-platform-devs; do
  GID=$(az ad group show --group $g --query id -o tsv)
  az rest --method POST --url "https://graph.microsoft.com/v1.0/servicePrincipals/$API_SP_ID/appRoleAssignedTo" \
    --headers "Content-Type=application/json" \
    --body "{\"principalId\":\"$GID\",\"resourceId\":\"$API_SP_ID\",\"appRoleId\":\"00000000-0000-0000-0000-000000000000\"}"
done

# Test users (or reuse existing accounts). Membership: A = eng-all + payments, B = eng-all + platform.
az ad group member add --group sdlc-eng-all       --member-id <user-A-oid>
az ad group member add --group sdlc-payments-devs --member-id <user-A-oid>
az ad group member add --group sdlc-eng-all       --member-id <user-B-oid>
az ad group member add --group sdlc-platform-devs --member-id <user-B-oid>
```

Then put the real group object IDs into `config/env/local/groups.yaml`. The aliases on the left
stay the same; only the `id` values change:

```bash
for g in sdlc-eng-all sdlc-payments-devs sdlc-platform-devs; do
  echo "$g $(az ad group show --group $g --query id -o tsv)"; done
```

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

## 4. Optional: Graph fallback for users with too many groups

This is only needed when a user's token can overflow (>200 groups, e.g. with `SecurityGroup`).
Without it, such users get **no groups** (fail closed) and `whoami` reports `group_source: overage_unresolved`.

```bash
GRAPH=00000003-0000-0000-c000-000000000000
GMRA=$(az ad sp show --id $GRAPH --query "appRoles[?value=='GroupMember.Read.All'].id" -o tsv)
az ad app permission add --id $API_APP_ID --api $GRAPH --api-permissions $GMRA=Role
az ad app permission admin-consent --id $API_APP_ID
az ad app credential reset --id $API_APP_ID --display-name graph-groups --years 1 --query password -o tsv
# -> .env: ENTRA_GRAPH_CLIENT_SECRET=<value>
```

## 5. Fill `.env` and verify

```dotenv
ENTRA_TENANT_ID=<tenant id>
ENTRA_API_CLIENT_ID=<sdlc-mcp client id>
ENTRA_CLIENT_ID=<sdlc-client client id>          # Stage 2d
ENTRA_CLIENT_SECRET=<sdlc-client secret>          # Stage 2d
ENTRA_GRAPH_CLIENT_SECRET=                        # optional (step 4)
```

```bash
uv run --env-file .env sdlc-config validate --env local
docker compose up -d --build --wait mcp-bootstrap

# Stage 2 check, before 2d: sign in as each test user and compare whoami.
az login --tenant $TENANT_ID --allow-no-subscriptions            # as user A
uv run python scripts/mcp_whoami.py --token "$(az account get-access-token \
  --scope api://sdlc-mcp/access_as_user --query accessToken -o tsv)"
# repeat as user B: groups must differ; a request with no/invalid token gets 401
```

Troubleshooting:
- **401 with a real token:** decode it at https://jwt.ms and check that `iss` ends in `/v2.0`,
  `aud` is the `sdlc-mcp` client ID, `scp` contains `access_as_user`, and `tid` matches.
- **`groups` missing or empty:** check that the group is assigned to the enterprise app, the user
  is a member, and `groupMembershipClaims` is set. Sign out and in again to get a fresh token.
- **AADSTS65001 (consent):** run admin consent for `sdlc-client`, or re-check `preAuthorizedApplications`.
