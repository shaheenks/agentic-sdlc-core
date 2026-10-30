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

# gcs sources (version-01 M2): read-only access for the ingest job, per bucket, no keys.
resource "google_storage_bucket_iam_member" "gcs_sources" {
  for_each = toset(var.gcs_source_buckets)
  bucket   = each.value
  role     = "roles/storage.objectViewer"
  member   = google_service_account.w["jobs"].member
}

# User connections (version-01 M6): the MCP server alone reads and writes users' own connection
# tokens, one secret per user named sdlc-<env>-user-<hash>. A custom role on that name prefix only
# (IAM condition); ingest and the agent get nothing. Check in M7 that the condition also covers
# secrets.create (the new secret's name); if not, an admin job creates the secret on first connect.
resource "google_project_iam_custom_role" "user_secrets" {
  role_id = "sdlcUserSecrets_${replace(var.env, "-", "_")}"
  title   = "agentic-sdlc ${var.env} user connection secrets"
  permissions = [
    "secretmanager.secrets.create",
    "secretmanager.secrets.get",
    "secretmanager.secrets.delete",
    "secretmanager.versions.add",
    "secretmanager.versions.access",
    "secretmanager.versions.list",
    "secretmanager.versions.destroy",
  ]
}

resource "google_project_iam_member" "mcp_user_secrets" {
  project = var.project_id
  role    = google_project_iam_custom_role.user_secrets.id
  member  = google_service_account.w["mcp"].member
  condition {
    title      = "user connection secrets only"
    expression = "resource.name.startsWith(\"projects/${data.google_project.this.number}/secrets/sdlc-${var.env}-user-\")"
  }
}
