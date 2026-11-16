# The chat UI on the native stack (CH-0016): sdlc-ui-native, the ui-copilotkit image behind IAP,
# talking to the user agent on Agent Runtime and to sdlc-mcp-native. Only with native_enabled and
# native_ui_enabled.
#
# Who may open it: members of var.iap_access_group (IAP, roles/iap.httpsResourceAccessor); IAP's
# service agent is the only invoker, so nothing reaches the container without IAP. The UI then
# gets the user's own Google ID token with a server-side sign-in (the Web OAuth client) and checks
# it names the IAP user before forwarding it. Its own service account may query Agent Runtime and
# invoke sdlc-mcp-native (Cloud Run IAM); it never speaks for a user without the user's token.

locals {
  ui_native_on   = var.native_enabled && var.native_ui_enabled
  ui_native_name = "sdlc-ui-native"
  ui_native_host = "${local.ui_native_name}-${data.google_project.this.number}.${var.region}.run.app"
  # the engine, from the agent's identity principal (.../resources/aiplatform/projects/<n>/locations/<r>/reasoningEngines/<id>)
  agent_engine = try(regex("resources/aiplatform/(projects/[^/]+/locations/[^/]+/reasoningEngines/[0-9]+)$", var.agent_runtime_principal)[0], "")
  # declared once, in config (platform.yaml identity.google), as for the agent and the MCP server
  google_allowed_domains = join(",", try(yamldecode(file("${path.module}/../../config/platform.yaml")).identity.google.allowed_domains, []))

  ui_native_env = {
    SDLC_AGENT_BACKEND        = "agent-runtime"
    SDLC_AGENT_ENGINE         = local.agent_engine
    SDLC_IAP_AUDIENCE         = "/projects/${data.google_project.this.number}/locations/${var.region}/services/${local.ui_native_name}"
    SDLC_OAUTH_CLIENT_IDS     = var.google_oauth_client_ids
    SDLC_ALLOWED_DOMAINS      = local.google_allowed_domains
    SDLC_GOOGLE_WEB_CLIENT_ID = var.google_web_client_id
    SDLC_PUBLIC_URL           = "https://${local.ui_native_host}"
    SDLC_MCP_BASE_URL         = "https://${local.mcp_native_host}"

    NEXT_TELEMETRY_DISABLED       = "1"
    COPILOTKIT_TELEMETRY_DISABLED = "true"
    DO_NOT_TRACK                  = "1"
  }
  ui_native_secret_env = {
    SDLC_GOOGLE_WEB_CLIENT_SECRET = "google-web-client-secret"
    SDLC_SESSION_KEY              = "ui-session-key"
  }
}

# The session cookie key (AES-256-GCM): 32 random bytes, base64url, kept in Secret Manager.
resource "random_id" "ui_session_key" {
  count       = local.ui_native_on ? 1 : 0
  byte_length = 32
}

resource "google_cloud_run_v2_service" "ui_native" {
  count                = local.ui_native_on ? 1 : 0
  name                 = local.ui_native_name
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL"
  launch_stage         = "BETA" # direct IAP on Cloud Run
  iap_enabled          = true
  invoker_iam_disabled = false
  deletion_protection  = var.deletion_protection

  template {
    service_account                  = google_service_account.w["ui-native"].email
    timeout                          = "3600s" # streamed agent responses
    max_instance_request_concurrency = 40
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
    containers {
      image   = local.images.ui
      command = ["node", "native-entry.mjs"] # maps /me, /threads, /connections/, /artifacts/ (ui/copilotkit)
      ports {
        container_port = 3000
      }
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
      dynamic "env" {
        for_each = local.ui_native_env
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = local.ui_native_secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = local.secret[env.value]
              version = "latest"
            }
          }
        }
      }
      startup_probe {
        http_get {
          path = "/chat/api/healthz"
        }
        period_seconds    = 5
        failure_threshold = 12
      }
    }
  }

  lifecycle {
    precondition {
      condition     = local.agent_engine != ""
      error_message = "native_ui_enabled needs agent_runtime_principal (the engine the UI talks to)."
    }
    precondition {
      condition     = var.google_web_client_id != "" && var.google_web_client_secret != "" && var.google_oauth_client_ids != ""
      error_message = "native_ui_enabled needs SDLC_GOOGLE_WEB_CLIENT_ID, SDLC_GOOGLE_WEB_CLIENT_SECRET and SDLC_OAUTH_CLIENT_IDS in .env."
    }
    precondition {
      condition     = local.google_allowed_domains != ""
      error_message = "native_ui_enabled needs identity.google.allowed_domains in config/platform.yaml."
    }
  }

  depends_on = [google_secret_manager_secret_version.s, google_secret_manager_secret_iam_member.w]
}

# IAP's service agent is the service's only invoker: every request has passed IAP.
resource "google_cloud_run_v2_service_iam_member" "ui_native_iap" {
  count    = local.ui_native_on ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.ui_native[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

# Who may pass IAP: one Cloud Identity group (dev: the group that mirrors SDLC.User).
resource "google_iap_web_cloud_run_service_iam_member" "ui_native_access" {
  count                  = local.ui_native_on && var.iap_access_group != "" ? 1 : 0
  project                = var.project_id
  location               = var.region
  cloud_run_service_name = google_cloud_run_v2_service.ui_native[0].name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = "group:${var.iap_access_group}"
}

# The UI calls sdlc-mcp-native for /connections/ and /artifacts/ (the user's token decides what).
resource "google_cloud_run_v2_service_iam_member" "mcp_native_ui" {
  count    = local.ui_native_on ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.mcp["native"].name
  role     = "roles/run.invoker"
  member   = google_service_account.w["ui-native"].member
}

# IAP's sign-in uses our own OAuth client (sdlc-iap-web), not the Google-managed one: that one admits
# only accounts of the project's organisation, and the users are accounts of another Cloud Identity
# organisation (dev, 2026-11-16: a member of every group was refused before any group check). The
# client's audience must admit those accounts; its redirect URI is
# https://iap.googleapis.com/v1/oauth/clientIds/<client id>:handleRedirect. The secret is kept in
# state, as the other client secrets.
resource "google_iap_settings" "ui_native" {
  count = local.ui_native_on ? 1 : 0
  name  = "projects/${data.google_project.this.number}/iap_web/cloud_run-${var.region}/services/${google_cloud_run_v2_service.ui_native[0].name}"

  access_settings {
    oauth_settings {
      client_id     = var.google_iap_client_id
      client_secret = var.google_iap_client_secret
      login_hint    = split(",", local.google_allowed_domains)[0] # the account picker's domain; not access control
    }
  }

  lifecycle {
    precondition {
      condition     = var.google_iap_client_id != "" && var.google_iap_client_secret != ""
      error_message = "native_ui_enabled needs SDLC_GOOGLE_IAP_CLIENT_ID and SDLC_GOOGLE_IAP_CLIENT_SECRET in .env (the sdlc-iap-web OAuth client)."
    }
  }
}
