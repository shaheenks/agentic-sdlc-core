# One service account per workload, least privilege. Vertex AI through the service identity.

locals {
  workloads = {
    mcp  = { roles = ["roles/cloudsql.client", "roles/aiplatform.user"], secrets = ["pg-app-password", "groups-yaml", "entra-graph-secret"] }
    app  = { roles = ["roles/aiplatform.user"], secrets = ["oauth2-cookie", "entra-client-secret"] }
    jobs = { roles = ["roles/cloudsql.client", "roles/aiplatform.user"], secrets = ["pg-admin-password", "pg-owner-password", "pg-app-password", "pg-ingest-password", "groups-yaml"] }
  }
  role_grants = merge([
    for w, spec in local.workloads : { for r in spec.roles : "${w}/${r}" => { workload = w, role = r } }
  ]...)
  secret_grants = merge([
    for w, spec in local.workloads : {
      for s in spec.secrets : "${w}/${s}" => { workload = w, secret = s }
      if contains(keys(google_secret_manager_secret.s), s)
    }
  ]...)
}

resource "google_service_account" "w" {
  for_each     = local.workloads
  account_id   = "sdlc-${var.env}-${each.key}"
  display_name = "agentic-sdlc ${var.env} ${each.key}"
}

resource "google_project_iam_member" "w" {
  for_each = local.role_grants
  project  = var.project_id
  role     = each.value.role
  member   = google_service_account.w[each.value.workload].member
}

resource "google_secret_manager_secret_iam_member" "w" {
  for_each  = local.secret_grants
  secret_id = google_secret_manager_secret.s[each.value.secret].id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.w[each.value.workload].member
}
