# Secret Manager secrets (NFR-SEC-004): containers only; versions are added by hand, never by Terraform,
# so no secret value is in the Terraform state. Each reaches its services as an environment variable.
locals {
  secrets = {
    "data-encryption-key"  = ["user_agent_mcp"]
    "sdlc-ui-oauth-client" = ["sdlc_ui"]
    "sdlc-ui-cookie-key"   = ["sdlc_ui"]
    "webhook-github"       = ["event_gateway"]
    "webhook-bitbucket"    = ["event_gateway"]
    "webhook-jira"         = ["event_gateway"]
    "system-pat-github"    = ["event_agent_mcp", "code_workspace", "event_gateway"] # the gateway: simulated events (DEC-0016)
    "system-pat-bitbucket" = ["event_agent_mcp", "code_workspace"]
    "system-pat-jira"      = ["event_agent_mcp"]
  }
  secret_access = merge([
    for secret, readers in local.secrets : { for r in readers : "${secret}/${r}" => { secret = secret, reader = r } }
  ]...)
}

resource "google_secret_manager_secret" "platform" {
  for_each  = local.secrets
  secret_id = "${local.prefix}-${each.key}"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "readers" {
  for_each  = local.secret_access
  secret_id = google_secret_manager_secret.platform[each.value.secret].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.component[each.value.reader].email}"
}
