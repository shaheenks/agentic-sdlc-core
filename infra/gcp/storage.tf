# Two private buckets (version-02), each created only when its variable is set:
# - config store: config bundles (bundles/<env>/, read by the MCP service and the ingest job,
#   run.tf) and source content for `gcs` sources under source_docs/<source id>/ (the former
#   repo samples/ corpus, read by the ingest job).
# - artifact store: temporary files and agent artefacts, written by the agent, deleted after
#   artifact_retention_days.

resource "google_storage_bucket" "config_store" {
  count    = var.config_store_bucket == "" ? 0 : 1
  name     = var.config_store_bucket
  location = var.region

  uniform_bucket_level_access = true       # IAM only, no object ACLs
  public_access_prevention    = "enforced" # never public, whatever IAM says
  force_destroy               = !var.deletion_protection

  versioning {
    enabled = true # overwritten or deleted content can be restored
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 5 # keep the last 5 old versions of each object
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    app = "agentic-sdlc"
    env = var.env
  }

  depends_on = [google_project_service.apis]
}

# The MCP service and the ingest job read it (config bundles under bundles/<env>/, source content);
# no keys, their own service accounts. Uploads are done by people with their own access
# (gcp_deploy.ps1 -Step config, gcloud storage cp), never by a service.
resource "google_storage_bucket_iam_member" "config_store_mcp" {
  count  = var.config_store_bucket == "" ? 0 : 1
  bucket = google_storage_bucket.config_store[0].name
  role   = "roles/storage.objectViewer"
  member = google_service_account.w["mcp"].member
}

resource "google_storage_bucket_iam_member" "config_store_reconcile" {
  count  = var.config_store_bucket == "" ? 0 : 1
  bucket = google_storage_bucket.config_store[0].name
  role   = "roles/storage.objectViewer"
  member = google_service_account.w["reconcile"].member
}

resource "google_storage_bucket_iam_member" "config_store_ingest" {
  count  = var.config_store_bucket == "" ? 0 : 1
  bucket = google_storage_bucket.config_store[0].name
  role   = "roles/storage.objectViewer"
  member = google_service_account.w["jobs"].member
}

resource "google_storage_bucket" "artifact_store" {
  count    = var.artifact_store_bucket == "" ? 0 : 1
  name     = var.artifact_store_bucket
  location = var.region

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = !var.deletion_protection

  # Temporary content: no versioning, no soft-delete window; objects go after the retention.
  soft_delete_policy {
    retention_duration_seconds = 0
  }

  lifecycle_rule {
    condition {
      age = var.artifact_retention_days
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    app = "agentic-sdlc"
    env = var.env
  }

  depends_on = [google_project_service.apis]
}

# The agent (sdlc-app service account) creates, reads and deletes its artefacts; nothing else
# gets access. Per-user separation is the agent web app's job (artefacts are keyed by app, user
# and session), as for conversations.
resource "google_storage_bucket_iam_member" "artifact_store_agent" {
  count  = var.artifact_store_bucket == "" ? 0 : 1
  bucket = google_storage_bucket.artifact_store[0].name
  role   = "roles/storage.objectUser"
  member = google_service_account.w["app"].member
}
