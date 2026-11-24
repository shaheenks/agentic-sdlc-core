# Knowledge (components ingest-pipeline, knowledge-store, knowledge-search; NFR-ARCH-004, DEC-0011).
#
# A refresh is one Cloud Build run (knowledge_ingest/cloudbuild.yaml) as the knowledge_ingest service account:
# ingest into the JSONL store, keep the store in the knowledge bucket for the next incremental run, build the
# Knowledge Search image with the store inside, and roll it out. Knowledge Search has internal ingress only and
# admits user_agent_mcp's service account; it is created once its first image exists (knowledge_search_image).

locals {
  knowledge_search_name = "knowledge-search"
  knowledge_search_url  = "https://${local.knowledge_search_name}-${data.google_project.this.number}.${var.region}.run.app"
  knowledge_callers     = ["user_agent_mcp"] # event_agent_mcp joins with the event path
  ingest                = google_service_account.component["knowledge_ingest"]
}

# The last store (read by the next run, so only changed files are embedded again) and the build's source.
resource "google_storage_bucket" "knowledge" {
  name                        = "${var.project_id}-${local.prefix}-knowledge"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  lifecycle_rule {
    condition {
      age            = 7
      matches_prefix = ["source/"]
    }
    action {
      type = "Delete"
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "knowledge_ingest" {
  bucket = google_storage_bucket.knowledge.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.ingest.email}"
}

# Ingest reads the active configuration's sources.
resource "google_storage_bucket_iam_member" "config_ingest" {
  bucket = google_storage_bucket.config.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${local.ingest.email}"
}

# Embeddings (ingest and queries) and concept extraction (ingest) on Vertex AI.
resource "google_project_iam_member" "knowledge_vertex" {
  for_each = toset(["knowledge_ingest", "knowledge_search"])
  project  = var.project_id
  role     = "roles/aiplatform.user"
  member   = "serviceAccount:${google_service_account.component[each.value].email}"
}

# The pipeline pushes the Knowledge Search image and rolls the service out to it.
resource "google_artifact_registry_repository_iam_member" "knowledge_ingest_writer" {
  repository = google_artifact_registry_repository.images.name
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${local.ingest.email}"
}

resource "google_service_account_iam_member" "ingest_acts_as_knowledge_search" {
  service_account_id = google_service_account.component["knowledge_search"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.ingest.email}"
}

# People who may start a refresh (gcloud builds submit --service-account=<knowledge_ingest account>).
resource "google_service_account_iam_member" "knowledge_refreshers" {
  for_each           = toset(var.knowledge_refreshers)
  service_account_id = local.ingest.name
  role               = "roles/iam.serviceAccountUser"
  member             = each.value
}

resource "google_cloud_run_v2_service" "knowledge_search" {
  count               = var.knowledge_search_image == "" ? 0 : 1
  name                = local.knowledge_search_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = false

  template {
    service_account = google_service_account.component["knowledge_search"].email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = var.knowledge_search_image

      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }

      env {
        name  = "SDLC_ENV"
        value = var.env
      }
      env {
        name  = "PUBLIC_URL"
        value = local.knowledge_search_url
      }
      env {
        name  = "ALLOWED_CALLERS"
        value = join(",", [for c in local.knowledge_callers : google_service_account.component[c].email])
      }
      env {
        name  = "EMBEDDINGS"
        value = "vertex"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "VERTEX_LOCATION"
        value = var.region
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
      }
      liveness_probe {
        http_get {
          path = "/healthz"
        }
      }
    }
  }

  lifecycle {
    # Each refresh rolls out a new image (knowledge_ingest/cloudbuild.yaml); Terraform sets only the first.
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_project_iam_member.knowledge_vertex]
}

resource "google_cloud_run_v2_service_iam_member" "knowledge_search_invokers" {
  for_each = var.knowledge_search_image == "" ? toset([]) : toset(local.knowledge_callers)
  name     = google_cloud_run_v2_service.knowledge_search[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.component[each.value].email}"
}

# The pipeline rolls out new revisions of this service only.
resource "google_cloud_run_v2_service_iam_member" "knowledge_search_deployer" {
  count    = var.knowledge_search_image == "" ? 0 : 1
  name     = google_cloud_run_v2_service.knowledge_search[0].name
  location = var.region
  role     = "roles/run.developer"
  member   = "serviceAccount:${local.ingest.email}"
}
