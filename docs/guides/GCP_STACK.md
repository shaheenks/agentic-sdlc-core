# GCP stack setup (Google identity, CH-0021 and CH-0022)

The GCP stack identifies users by their **Google ID token** and takes membership from **Google groups** in Cloud
Identity, beside the unchanged Entra stack. This guide sets up what it needs outside the repo, runs it locally
(compose profile `gcp`) and rolls it out to GCP (`sdlc-mcp-native` + the agent on Agent Runtime).

Everything here is done by you: Admin console, Cloud console, `.env`, Terraform and deploys. Nothing in this guide
is committed except the group emails and the allowed domain (already in `config/`).

What the repo already declares:
- `config/platform.yaml` `identity.google`: the allowed Cloud Identity domain, `group_lookup: direct` (Cloud
  Identity Free: direct members only, no nested groups).
- `config/roles.yaml` and `config/teams/*.yaml`: one `group:` beside each `app_role:` (`SDLC.Payments.Member` ->
  `sdlc-payments-member@<domain>`). `uv run sdlc-config validate --env local` checks that every persona gets the
  same access from its groups as from its app roles.

## 1. Cloud Identity (Admin console, admin.google.com)

1. **Users**: every user has an account in the allowed domain. Consumer `@gmail.com` accounts are always refused
   (no `hd` claim).
2. **Groups**: one per app role (already created). Add people **directly** (no nested groups) and put every user
   in `sdlc-user@` as well as their team groups.
3. **Groups Reader** for the server, after the Terraform apply in step 5: *Account > Admin roles > Groups Reader >
   Admins > Assign service accounts*, enter `terraform output -raw mcp_gcp_service_account`
   (`sdlc-<env>-mcp-gcp@<project>.iam.gserviceaccount.com`). Without it every lookup gets 403 and users get only
   `ping` and `whoami` (fail closed).

## 2. OAuth clients (Cloud console, the GCP project)

1. *APIs & Services > OAuth consent screen*: user type **Internal**, app name, support email. Scopes: `openid`,
   `email`, `profile`.
2. *Credentials > Create OAuth client ID > **Web application*** (the sign-in proxies):
   - Authorised redirect URIs:
     - `http://localhost:4190/oauth2/callback` (local, compose profile `gcp`)
     - `https://<SDLC_GCP_APP_HOST>/oauth2/callback` (the tunnel, profile `gcp-tunnel`; add the hostname in the
       Cloudflare dashboard -> `http://localhost:4191`)
   - The UI on GCP (CH-0016) adds its own URI when it moves.
3. *Credentials > Create OAuth client ID > **Desktop app*** (`scripts/google_id_token.py`, manual checks). No
   redirect URI to register: it uses a loopback address.

The ID token's audience is the client that signed the user in, so **both client IDs** go into
`SDLC_OAUTH_CLIENT_IDS`. Client IDs are not secret but are never committed.

## 3. `.env`

```
# GCP stack (docs/guides/GCP_STACK.md)
SDLC_OAUTH_CLIENT_IDS=<web client id>,<desktop client id>
SDLC_ALLOWED_DOMAINS=<cloud identity domain>      # same as platform.yaml identity.google (agent, proxy)
SDLC_GOOGLE_WEB_CLIENT_ID=<web client id>
SDLC_GOOGLE_WEB_CLIENT_SECRET=<web client secret>
SDLC_GOOGLE_DESKTOP_CLIENT_ID=<desktop client id>
SDLC_GOOGLE_DESKTOP_CLIENT_SECRET=<desktop client secret>
# SDLC_GCP_APP_HOST=app-gcp-sdlc-dev.<domain>      # tunnel hostnames (defaults in docker-compose.yml)
# SDLC_GCP_MCP_HOST=mcp-gcp-sdlc-dev.<domain>
```

## 4. Local: compose profile `gcp`

The local server reads groups as **your** Application Default Credentials (the account must be able to see the
groups' members, e.g. a group manager or an admin of the domain). Give ADC the Groups scope and a billing
project with the Cloud Identity API enabled:

```
gcloud auth application-default login --scopes=openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/cloud-identity.groups.readonly
gcloud auth application-default set-quota-project <project>
```

`GOOGLE_CLOUD_QUOTA_PROJECT` in `.env` (already used for Vertex AI) is sent as the billing project.

```
docker compose --profile gcp up -d --build          # + --profile gcp-tunnel for the public proxy
```

- Sign in at http://localhost:4190 (adk web on the GCP stack's agent). The chat app stays on the Entra stack
  (http://localhost:4180/chat/) until the UI moves (CH-0016).
- `uv run --env-file .env python scripts/mcp_whoami.py --idp google --url http://127.0.0.1:8090/mcp --explain`
  signs you in in the browser and shows your groups, teams and roles with the rules behind them.

## 5. GCP rollout (you run these; dev)

Commit first: images and the plan use the commit as their tag.

1. `.\scripts\gcp_deploy.ps1 -EnvName dev -Step images` (builds `core-mcp-gcp` too).
2. `.\scripts\gcp_deploy.ps1 -EnvName dev -Step plan`, review, then `-Step apply`. Expect: the
   `sdlc-dev-mcp-gcp` service account and its grants, `cloudidentity.googleapis.com`, `sdlc-mcp-native` on the
   new image and account with `SDLC_OAUTH_CLIENT_IDS` instead of `ENTRA_*`, the gateway endpoint
   `google-signing-keys` replacing `entra-signing-keys`. `sdlc-mcp-dev` and `sdlc-app-dev` should show no
   change (the Entra service gets the same `ENTRA_*` variables, now from `mcp_identity_env`).
3. Groups Reader for `terraform output -raw mcp_gcp_service_account` (step 1.3).
4. `.\scripts\gcp_deploy.ps1 -EnvName dev -Step config` (the bundle with the group bindings).
5. `.\scripts\gcp_deploy.ps1 -EnvName dev -Step db` (migration `009_owner_id_shapes.sql`).
6. `uv run --env-file .env python scripts/deploy_agent_runtime.py --env dev` (`--idp google` is the default;
   the engine is updated in place, so its Agent Identity and the invoker grant stay the same). Until this runs
   the engine still expects Entra tokens, and with the gateway enforced it can no longer fetch Entra's keys:
   run steps 2 and 6 together.

Rollback: `deploy_agent_runtime.py --idp entra` with the previous commit's Terraform (Entra keys endpoint).

## 6. Verify

- `uv run --env-file .env python scripts/agent_runtime_query.py --idp google "Call whoami with explain=true."`
  answers as you, with your groups behind each role; `--token <Entra token>` is refused (`unauthenticated`).
- A user in no group gets `ping` and `whoami` only; a user outside the domain is refused.
- Logs: `tool_call` records with `"idp":"google"` from `sdlc-mcp-native`; the Entra stack (`sdlc-mcp-dev`,
  `sdlc-app-dev`) answers as before.
