# sdlc_ui on Cloud Run behind IAP, and user_agent on Agent Runtime (components sdlc-ui, agent-runtime; DEC-0010).
#
# - IAP lets in the members of var.sdlc_ui_users; its service agent is the service's only invoker, so every
#   request has passed IAP. sdlc_ui verifies IAP's signed assertion and forwards the user's ID and email.
# - sdlc_ui's service account may query Agent Runtime (user_agent, deployed by
#   interactive_agents/user_agent/deploy.py) and invoke user_agent_mcp.
# - user_agent runs as the interactive agents' service account: Gemini and its sessions on Vertex AI, and
#   user_agent_mcp, which knows that account as the `user_agent` caller.
# The service is created once its image and the agent engine exist (sdlc_ui_image, agent_engine).

locals {
  sdlc_ui_name = "sdlc-ui"
  sdlc_ui_url  = "https://${local.sdlc_ui_name}-${data.google_project.this.number}.${var.region}.run.app"
  sdlc_ui_on   = var.sdlc_ui_image != "" && var.agent_engine != ""
}

# Querying Agent Runtime (sdlc_ui) and running the agent: Gemini and sessions (interactive agents).
resource "google_project_iam_member" "agent_runtime_users" {
  for_each = toset(["sdlc_ui", "interactive_agents"])
  project  = var.project_id
  role     = "roles/aiplatform.user"
  member   = "serviceAccount:${google_service_account.component[each.value].email}"
}

resource "google_cloud_run_v2_service" "sdlc_ui" {
  count                = local.sdlc_ui_on ? 1 : 0
  name                 = local.sdlc_ui_name
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL"
  deletion_protection  = false
  iap_enabled          = true
  invoker_iam_disabled = false

  template {
    service_account = google_service_account.component["sdlc_ui"].email
    # A chat run streams through this service for as long as the agent works: a workflow (drafting, then seven
    # reviewers per round over several rounds) can take well over the default five minutes. Cloud Run's maximum.
    timeout = "3600s"

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = var.sdlc_ui_image

      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }

      env {
        name  = "SDLC_ENV"
        value = var.env
      }
      env {
        name  = "SDLC_AUTH"
        value = "iap"
      }
      env {
        name  = "SDLC_IAP_AUDIENCE"
        value = "/projects/${data.google_project.this.number}/locations/${var.region}/services/${local.sdlc_ui_name}"
      }
      env {
        name  = "SDLC_AGENT_URL"
        value = "https://${var.region}-aiplatform.googleapis.com/v1/${var.agent_engine}"
      }
      env {
        name  = "SDLC_MCP_URL"
        value = local.user_agent_mcp_url
      }

      startup_probe {
        http_get {
          path = "/api/healthz"
        }
      }
    }
  }

  depends_on = [google_project_iam_member.agent_runtime_users]
}

# IAP's service agent is the only invoker: nothing reaches the container without passing IAP.
resource "google_cloud_run_v2_service_iam_member" "sdlc_ui_iap" {
  count    = local.sdlc_ui_on ? 1 : 0
  name     = google_cloud_run_v2_service.sdlc_ui[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

# Who may pass IAP (user:, group: or domain: members).
resource "google_iap_web_cloud_run_service_iam_member" "sdlc_ui_users" {
  for_each               = local.sdlc_ui_on ? toset(var.sdlc_ui_users) : toset([])
  project                = var.project_id
  location               = var.region
  cloud_run_service_name = google_cloud_run_v2_service.sdlc_ui[0].name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = each.value
}

# IAP signs in with our own OAuth client when one is given: the Google-managed client admits only accounts of
# the project's own organisation. Its redirect URI is
# https://iap.googleapis.com/v1/oauth/clientIds/<client id>:handleRedirect. The secret ends up in state.
resource "google_iap_settings" "sdlc_ui" {
  count = local.sdlc_ui_on && var.iap_oauth_client_id != "" ? 1 : 0
  name  = "projects/${data.google_project.this.number}/iap_web/cloud_run-${var.region}/services/${local.sdlc_ui_name}"

  access_settings {
    oauth_settings {
      client_id     = var.iap_oauth_client_id
      client_secret = var.iap_oauth_client_secret
    }
  }

  depends_on = [google_cloud_run_v2_service.sdlc_ui]
}
