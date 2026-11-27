# The event path of phase 5a (DEC-0007, DEC-0015): event_gateway (public, webhooks verified by signature), a Cloud
# Tasks queue, the event agents' Agent Runtime engine (deployed by event_based_agents/ci_workflow_agent/deploy.py),
# event_agent_mcp (the system identity's tools) and the Code Workspace job. Each service is created once its image
# (and, for the gateway, the engine) is set, so this file can be applied step by step.

locals {
  event_agent_mcp_name = "event-agent-mcp"
  event_agent_mcp_url  = "https://${local.event_agent_mcp_name}-${data.google_project.this.number}.${var.region}.run.app"
  event_gateway_name   = "event-gateway"
  event_gateway_url    = "https://${local.event_gateway_name}-${data.google_project.this.number}.${var.region}.run.app"
  code_workspace_name  = "${local.prefix}-code-workspace"
  code_workspace_job   = "projects/${var.project_id}/locations/${var.region}/jobs/${local.code_workspace_name}"

  event_agent_mcp_on = var.event_agent_mcp_image != ""
  event_gateway_on   = var.event_gateway_image != "" && var.event_agent_engine != ""
  code_workspace_on  = var.code_workspace_image != ""
  # The credential-free Code Workspace job for user_agent_mcp (DEC-0016): same image, no secret, its own prefix.
  code_workspace_user_name = "${local.prefix}-code-workspace-user"
  code_workspace_user_job  = "projects/${var.project_id}/locations/${var.region}/jobs/${local.code_workspace_user_name}"
  workspace_user_prefix    = "artifacts/user-runs/"

  # One Code Workspace execution; a run (25 minutes at most) needs room for a few (DEC-0015).
  workspace_timeout_seconds = 900
  # The run's prefix of the artifact bucket the Code Workspace reads requests from and writes results to.
  workspace_prefix = "artifacts/system/runs/"
}

resource "google_project_service" "cloudtasks" {
  service            = "cloudtasks.googleapis.com"
  disable_on_destroy = false
}

# The hand-off from the webhook to the run: one task per run, retried a few times; the run itself is idempotent.
resource "google_cloud_tasks_queue" "runs" {
  name     = "${local.prefix}-runs"
  location = var.region

  rate_limits {
    max_dispatches_per_second = 1
    max_concurrent_dispatches = 5
  }
  retry_config {
    max_attempts  = 3
    min_backoff   = "60s"
    max_backoff   = "600s"
    max_doublings = 3
  }
  depends_on = [google_project_service.cloudtasks]
}

# The system identity: the event agents' engine runs as it, calls Gemini and event_agent_mcp.
resource "google_project_iam_member" "event_agents_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.component["event_agents"].email}"
}

# The gateway starts runs on the engine (:query, :streamQuery) and reads the configuration.
resource "google_project_iam_member" "event_gateway_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.component["event_gateway"].email}"
}

resource "google_storage_bucket_iam_member" "event_gateway_config" {
  bucket = google_storage_bucket.config.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.component["event_gateway"].email}"
}

# Deliveries and runs under events/ of the artifact bucket (create-if-absent objects), deleted after 7 days.
resource "google_storage_bucket_iam_member" "event_gateway_events" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.component["event_gateway"].email}"
  condition {
    title       = "event-gateway-events"
    description = "Only the objects under events/"
    expression  = "resource.name.startsWith(\"${local.artifact_objects}/events/\")"
  }
}

# Tasks: the gateway enqueues, as itself, and the queue calls /run with an OIDC token of the same account.
resource "google_cloud_tasks_queue_iam_member" "event_gateway_enqueuer" {
  name     = google_cloud_tasks_queue.runs.id
  location = var.region
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${google_service_account.component["event_gateway"].email}"
}

resource "google_service_account_iam_member" "event_gateway_acts_as_itself" {
  service_account_id = google_service_account.component["event_gateway"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.component["event_gateway"].email}"
}

# The Code Workspace reads requests and writes results under artifacts/system/runs/ only.
resource "google_storage_bucket_iam_member" "code_workspace_runs" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.component["code_workspace"].email}"
  condition {
    title       = "code-workspace-runs"
    description = "Only the objects under ${local.workspace_prefix}"
    expression = join(" || ", [
      "resource.type == \"storage.googleapis.com/Bucket\"",
      "resource.name.startsWith(\"${local.artifact_objects}/${local.workspace_prefix}\")",
      "resource.name.startsWith(\"${local.artifact_folders}/${local.workspace_prefix}\")",
    ])
  }
}

# event_agent_mcp ---------------------------------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "event_agent_mcp" {
  count               = local.event_agent_mcp_on ? 1 : 0
  name                = local.event_agent_mcp_name
  location            = var.region
  ingress             = var.event_agent_mcp_ingress
  deletion_protection = false

  template {
    service_account       = google_service_account.component["event_agent_mcp"].email
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
    timeout               = "${local.workspace_timeout_seconds + 300}s" # workspace_run waits for the job
    labels = {
      store-access = substr(sha1(google_storage_bucket_iam_member.artifact_prefixes["event_agent_mcp"].condition[0].expression), 0, 12)
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    # GitHub and the other systems through Cloud NAT (network.tf).
    vpc_access {
      egress = "ALL_TRAFFIC"
      network_interfaces {
        network    = google_compute_network.platform.id
        subnetwork = google_compute_subnetwork.platform.id
      }
    }

    containers {
      image = var.event_agent_mcp_image
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
        value = local.event_agent_mcp_url
      }
      env {
        name  = "WORKSPACE_MODE"
        value = local.code_workspace_on ? "job" : ""
      }
      env {
        name  = "WORKSPACE_JOB"
        value = local.code_workspace_job
      }
      env {
        name  = "WORKSPACE_TIMEOUT_SECONDS"
        value = tostring(local.workspace_timeout_seconds)
      }
      env {
        name = "SYSTEM_TOKEN_GITHUB"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.platform["system-pat-github"].secret_id
            version = "latest"
          }
        }
      }
      volume_mounts {
        name       = "artifacts-system"
        mount_path = "/data/store/artifacts/system"
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

    volumes {
      name = "artifacts-system"
      gcs {
        bucket        = google_storage_bucket.artifacts.name
        read_only     = false
        mount_options = ["only-dir=artifacts/system"]
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_iam_member.readers,
    google_storage_bucket_iam_member.artifact_prefixes,
    google_storage_bucket_iam_member.config_readers,
  ]
}

# Only the event agents' engine calls it; the app then checks the ID token against identity.callers.event_agents.
resource "google_cloud_run_v2_service_iam_member" "event_agent_mcp_invoker" {
  count    = local.event_agent_mcp_on ? 1 : 0
  name     = google_cloud_run_v2_service.event_agent_mcp[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.component["event_agents"].email}"
}

# The Code Workspace job --------------------------------------------------------------------------------------------

resource "google_cloud_run_v2_job" "code_workspace" {
  count               = local.code_workspace_on ? 1 : 0
  name                = local.code_workspace_name
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1
    template {
      service_account       = google_service_account.component["code_workspace"].email
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
      timeout               = "${local.workspace_timeout_seconds}s"
      max_retries           = 0 # a failed execution is a result for the agent

      vpc_access {
        egress = "ALL_TRAFFIC"
        network_interfaces {
          network    = google_compute_network.platform.id
          subnetwork = google_compute_subnetwork.platform.id
        }
      }

      containers {
        image = var.code_workspace_image
        resources {
          limits = { cpu = "2", memory = "4Gi" }
        }
        env {
          name  = "STORE_MOUNT_PATH"
          value = "/data/store"
        }
        env {
          name  = "WORKSPACE_TIMEOUT_SECONDS"
          value = tostring(local.workspace_timeout_seconds - 60)
        }
        env {
          name = "SYSTEM_TOKEN_GITHUB"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.platform["system-pat-github"].secret_id
              version = "latest"
            }
          }
        }
        volume_mounts {
          name       = "runs"
          mount_path = "/data/store/${trimsuffix(local.workspace_prefix, "/")}"
        }
      }

      volumes {
        name = "runs"
        gcs {
          bucket        = google_storage_bucket.artifacts.name
          read_only     = false
          mount_options = ["only-dir=${trimsuffix(local.workspace_prefix, "/")}"]
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_iam_member.readers, google_storage_bucket_iam_member.code_workspace_runs]
}

# Only event_agent_mcp starts it, with its request path as an override.
resource "google_cloud_run_v2_job_iam_member" "code_workspace_runner" {
  count    = local.code_workspace_on ? 1 : 0
  name     = google_cloud_run_v2_job.code_workspace[0].name
  location = var.region
  role     = "roles/run.jobsExecutorWithOverrides"
  member   = "serviceAccount:${google_service_account.component["event_agent_mcp"].email}"
}

# event_gateway -----------------------------------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "event_gateway" {
  count               = local.event_gateway_on ? 1 : 0
  name                = local.event_gateway_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL" # webhooks from GitHub; every delivery is verified by its signature
  deletion_protection = false

  template {
    service_account = google_service_account.component["event_gateway"].email
    timeout         = "1800s" # /run follows the run (Cloud Tasks' dispatch deadline)

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = var.event_gateway_image
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
        name  = "PUBLIC_URL"
        value = local.event_gateway_url
      }
      env {
        name  = "EVENTS_BUCKET"
        value = google_storage_bucket.artifacts.name
      }
      env {
        name  = "TASKS_QUEUE"
        value = google_cloud_tasks_queue.runs.id
      }
      env {
        name  = "TASKS_INVOKER"
        value = google_service_account.component["event_gateway"].email
      }
      env {
        name  = "AGENT_URL"
        value = "https://${var.region}-aiplatform.googleapis.com/v1/${var.event_agent_engine}"
      }
      env {
        name = "SYSTEM_TOKEN_GITHUB" # reads pull requests for simulated events (FR-TRIG-006, DEC-0016)
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.platform["system-pat-github"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "WEBHOOK_SECRET_GITHUB"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.platform["webhook-github"].secret_id
            version = "latest"
          }
        }
      }
      startup_probe {
        http_get {
          path = "/healthz"
        }
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_iam_member.readers,
    google_storage_bucket_iam_member.event_gateway_config,
    google_storage_bucket_iam_member.event_gateway_events,
  ]
}

# Public: GitHub's webhooks carry no Google identity. The app refuses any delivery whose signature does not verify,
# and /run accepts only the queue's OIDC token for the gateway's own account (DEC-0015).
resource "google_cloud_run_v2_service_iam_member" "event_gateway_public" {
  count    = local.event_gateway_on ? 1 : 0
  name     = google_cloud_run_v2_service.event_gateway[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# The credential-free Code Workspace for user_agent_mcp (DEC-0016) ---------------------------------------------------
# It holds no token and pushes nothing: user_agent_mcp fetches the repository's archive with the user's connection,
# and commits the built change with it afterwards. It reads requests under artifacts/user-runs/ only.

resource "google_storage_bucket_iam_member" "code_workspace_user_runs" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.component["code_workspace_usr"].email}"
  condition {
    title       = "code-workspace-user-runs"
    description = "Only the objects under ${local.workspace_user_prefix}"
    expression = join(" || ", [
      "resource.type == \"storage.googleapis.com/Bucket\"",
      "resource.name.startsWith(\"${local.artifact_objects}/${local.workspace_user_prefix}\")",
      "resource.name.startsWith(\"${local.artifact_folders}/${local.workspace_user_prefix}\")",
    ])
  }
}

resource "google_cloud_run_v2_job" "code_workspace_user" {
  count               = local.code_workspace_on ? 1 : 0
  name                = local.code_workspace_user_name
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1
    template {
      service_account       = google_service_account.component["code_workspace_usr"].email
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
      timeout               = "${local.workspace_timeout_seconds}s"
      max_retries           = 0

      vpc_access {
        egress = "ALL_TRAFFIC" # package registries through Cloud NAT; no repository is reached
        network_interfaces {
          network    = google_compute_network.platform.id
          subnetwork = google_compute_subnetwork.platform.id
        }
      }

      containers {
        image = var.code_workspace_image
        resources {
          limits = { cpu = "2", memory = "4Gi" }
        }
        env {
          name  = "WORKSPACE_MODE"
          value = "user"
        }
        env {
          name  = "STORE_MOUNT_PATH"
          value = "/data/store"
        }
        env {
          name  = "WORKSPACE_TIMEOUT_SECONDS"
          value = tostring(local.workspace_timeout_seconds - 60)
        }
        volume_mounts {
          name       = "user-runs"
          mount_path = "/data/store/${trimsuffix(local.workspace_user_prefix, "/")}"
        }
      }

      volumes {
        name = "user-runs"
        gcs {
          bucket        = google_storage_bucket.artifacts.name
          read_only     = false
          mount_options = ["only-dir=${trimsuffix(local.workspace_user_prefix, "/")}"]
        }
      }
    }
  }

  depends_on = [google_storage_bucket_iam_member.code_workspace_user_runs]
}

# Only user_agent_mcp starts it, with its request path as an override.
resource "google_cloud_run_v2_job_iam_member" "code_workspace_user_runner" {
  count    = local.code_workspace_on ? 1 : 0
  name     = google_cloud_run_v2_job.code_workspace_user[0].name
  location = var.region
  role     = "roles/run.jobsExecutorWithOverrides"
  member   = "serviceAccount:${google_service_account.component["user_agent_mcp"].email}"
}
