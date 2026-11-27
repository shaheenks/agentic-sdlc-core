# Configuration bucket (FR-CFG-005): versioned, written only by the publishing pipeline, read by the MCP servers.
resource "google_storage_bucket" "config" {
  name                        = "${var.project_id}-${local.prefix}-config"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  versioning {
    enabled = true
  }
  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "config_readers" {
  for_each = toset(["user_agent_mcp", "event_agent_mcp"])
  bucket   = google_storage_bucket.config.name
  role     = "roles/storage.objectViewer"
  member   = "serviceAccount:${google_service_account.component[each.value].email}"
}

# Artifact bucket (FR-ART-003, DEC-0006): artifacts/ deleted after 7 days; users' encrypted connection secrets
# under secrets/users/. Each MCP server reaches only its own prefixes through IAM conditions.
resource "google_storage_bucket" "artifacts" {
  name                        = "${var.project_id}-${local.prefix}-artifacts"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    condition {
      age            = var.artifact_retention_days
      matches_prefix = ["artifacts/", "events/"] # events/: the event gateway's deliveries and runs (DEC-0015)
    }
    action {
      type = "Delete"
    }
  }
  depends_on = [google_project_service.apis]
}

locals {
  artifact_objects = "projects/_/buckets/${google_storage_bucket.artifacts.name}/objects"
  # Cloud Storage FUSE lists a mounted prefix as a folder (only-dir mounts), checked against this name.
  artifact_folders = "projects/_/buckets/${google_storage_bucket.artifacts.name}/folders"
  store_prefixes = {
    user_agent_mcp  = ["artifacts/users/", "secrets/users/", "artifacts/user-runs/"] # user-runs: DEC-0016
    event_agent_mcp = ["artifacts/system/"]
  }
}

resource "google_storage_bucket_iam_member" "artifact_prefixes" {
  for_each = local.store_prefixes
  bucket   = google_storage_bucket.artifacts.name
  role     = "roles/storage.objectUser"
  member   = "serviceAccount:${google_service_account.component[each.key].email}"
  condition {
    title       = "${each.key}-prefixes"
    description = "Only the objects under ${join(", ", each.value)}"
    expression = join(" || ", concat(
      ["resource.type == \"storage.googleapis.com/Bucket\""],
      [for p in each.value : "resource.name.startsWith(\"${local.artifact_objects}/${p}\")"],
      [for p in each.value : "resource.name.startsWith(\"${local.artifact_folders}/${p}\")"],
    ))
  }
}
