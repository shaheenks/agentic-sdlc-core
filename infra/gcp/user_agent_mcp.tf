# user_agent_mcp on Cloud Run (component user-agent-mcp; DEC-0002, DEC-0010).
# Callers prove themselves twice: Cloud Run invoker IAM, then the app checks the ID token's account against
# identity.callers in the active configuration. Ingress is `all` until sdlc_ui runs in this environment, so the
# deploy can be checked from outside; then it becomes internal.

data "google_project" "this" {}

locals {
  user_agent_mcp_name = "user-agent-mcp"
  # Cloud Run's deterministic URL; also the audience callers' ID tokens must carry (PUBLIC_URL).
  user_agent_mcp_url = "https://${local.user_agent_mcp_name}-${data.google_project.this.number}.${var.region}.run.app"
  # Who may call it for a user: sdlc_ui's BFF and the interactive agents on Agent Runtime.
  user_agent_mcp_callers = ["sdlc_ui", "interactive_agents"]
}

resource "google_cloud_run_v2_service" "user_agent_mcp" {
  name                = local.user_agent_mcp_name
  location            = var.region
  ingress             = var.user_agent_mcp_ingress
  deletion_protection = false

  template {
    service_account       = google_service_account.component["user_agent_mcp"].email
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2" # Cloud Storage volume mounts
    # A new revision whenever its bucket access changes, so the mounts are retried under the new conditions.
    labels = {
      store-access = substr(sha1(google_storage_bucket_iam_member.artifact_prefixes["user_agent_mcp"].condition[0].expression), 0, 12)
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = var.user_agent_mcp_image

      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }

      env {
        name  = "SDLC_ENV"
        value = var.env
      }
      env {
        name  = "CONFIG_SOURCE"
        value = "gs://${google_storage_bucket.config.name}"
      }
      env {
        name  = "STORE_MOUNT_PATH"
        value = "/data/store"
      }
      env {
        name  = "PUBLIC_URL"
        value = local.user_agent_mcp_url
      }
      dynamic "env" {
        for_each = var.sdlc_ui_url == "" ? [] : [var.sdlc_ui_url]
        content {
          name  = "SDLC_UI_URL"
          value = env.value
        }
      }
      env {
        name = "DATA_ENCRYPTION_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.platform["data-encryption-key"].secret_id
            version = "latest"
          }
        }
      }

      # One mount per prefix its IAM condition allows: Cloud Storage FUSE writes a folder object for every
      # directory it creates, so mounting the bucket root would need objects outside those prefixes.
      dynamic "volume_mounts" {
        for_each = local.store_prefixes.user_agent_mcp
        content {
          name       = replace(trimsuffix(volume_mounts.value, "/"), "/", "-")
          mount_path = "/data/store/${trimsuffix(volume_mounts.value, "/")}"
        }
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

    dynamic "volumes" {
      for_each = local.store_prefixes.user_agent_mcp
      content {
        name = replace(trimsuffix(volumes.value, "/"), "/", "-")
        gcs {
          bucket        = google_storage_bucket.artifacts.name
          read_only     = false
          mount_options = ["only-dir=${trimsuffix(volumes.value, "/")}"]
        }
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_iam_member.readers,
    google_storage_bucket_iam_member.artifact_prefixes,
    google_storage_bucket_iam_member.config_readers,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "user_agent_mcp_invokers" {
  for_each = toset(local.user_agent_mcp_callers)
  name     = google_cloud_run_v2_service.user_agent_mcp.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.component[each.value].email}"
}

# Development only: people who may mint sdlc_ui's ID token to call user_agent_mcp by hand
# (gcloud auth print-identity-token --impersonate-service-account=... --audiences=<url> --include-email).
resource "google_service_account_iam_member" "sdlc_ui_testers" {
  for_each           = toset(var.sdlc_ui_testers)
  service_account_id = google_service_account.component["sdlc_ui"].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = each.value
}
