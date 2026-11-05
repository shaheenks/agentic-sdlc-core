# Cloud Run: sdlc-mcp (public; the Entra token is the gate), sdlc-app (oauth2-proxy ingress + agent
# sidecar on localhost) and the jobs sdlc-db-setup / sdlc-ingest.
# Public without an allUsers binding (org policy iam.allowedPolicyMemberDomains): invoker_iam_disabled.

locals {
  secret = { for k, v in google_secret_manager_secret.s : k => v.secret_id }

  # Config bundles (version-02 N13): with a config store bucket, the MCP service and the ingest
  # job read the active bundle from gs://<bucket>/bundles/<env>/ (mounted read-only; published
  # by `gcp_deploy.ps1 -Step config`). A bundle carries config, skills and the tenant
  # groups.yaml / users.yaml, so the secret mounts for those files are not used then.
  bundles     = var.config_store_bucket != ""
  bundles_dir = "/app/config-bundles"
  bundles_env = local.bundles ? { SDLC_CONFIG_BUNDLES = local.bundles_dir } : {}
  # users.yaml as a secret mount only without bundles (version-02 N10)
  users_secret = !local.bundles && var.users_yaml_path != ""

  mcp_env = merge(
    local.vertex_env,
    local.entra_env,
    {
      SDLC_ENV                 = var.env
      SDLC_CONFIG_WATCH        = "false" # without bundles: config baked into the image per release
      SDLC_CONFIG_POLL_SECONDS = "60"    # with bundles: check the `current` pointer every minute
      MCP_PUBLIC_URL           = "https://${local.mcp_host}"
      PGHOST                   = local.cloudsql_socket
      PGDATABASE               = google_sql_database.sdlc.name
      PGUSER                   = "sdlc_app"
      # user connections (version-01 M6): users' own PATs, one Secret Manager secret per user
      SDLC_USER_SECRETS_BACKEND = "gcp"
      SDLC_SECRETS_PROJECT      = var.project_id
    },
    local.bundles_env,
    local.trace_env,
    # direct members (version-02 N10) without bundles: read from the secret mount
    local.users_secret ? { SDLC_USERS_FILE = "${local.users_dir}/users.yaml" } : {},
  )
  mcp_secret_env = merge(
    { PGPASSWORD = "pg-app-password" },
    contains(keys(local.secret), "entra-graph-secret") ? { ENTRA_GRAPH_CLIENT_SECRET = "entra-graph-secret" } : {},
  )

  # Same settings as the local oauth2-proxy (docker-compose.yml x-oauth2-proxy-env).
  oauth2_proxy_env = {
    OAUTH2_PROXY_PROVIDER              = "oidc"
    OAUTH2_PROXY_PROVIDER_DISPLAY_NAME = "Entra ID"
    OAUTH2_PROXY_OIDC_ISSUER_URL       = "${var.entra_authority_host}/${var.entra_tenant_id}/v2.0"
    OAUTH2_PROXY_CLIENT_ID             = var.entra_client_id
    OAUTH2_PROXY_SCOPE                 = "openid profile email offline_access api://${var.entra_api_client_id}/access_as_user"
    OAUTH2_PROXY_CODE_CHALLENGE_METHOD = "S256"
    OAUTH2_PROXY_PROMPT                = "select_account" # account picker at sign-in (after Sign out)
    # /chat/ -> CopilotKit app (sidecar), /connections/ -> MCP service (users' own connections),
    # everything else -> the agent (adk web, /agui). As in docker-compose.yml.
    OAUTH2_PROXY_UPSTREAMS = "http://127.0.0.1:8000/,http://127.0.0.1:3000/chat/,https://${local.mcp_host}/connections/"
    # Cloud Run routes by Host: the MCP upstream must get its own host, not the app's.
    OAUTH2_PROXY_PASS_HOST_HEADER                     = "false"
    OAUTH2_PROXY_HTTP_ADDRESS                         = "0.0.0.0:4180"
    OAUTH2_PROXY_PASS_ACCESS_TOKEN                    = "true"
    OAUTH2_PROXY_SKIP_PROVIDER_BUTTON                 = "true"
    OAUTH2_PROXY_OIDC_EMAIL_CLAIM                     = "preferred_username"
    OAUTH2_PROXY_SKIP_CLAIMS_FROM_PROFILE_URL         = "true"
    OAUTH2_PROXY_INSECURE_OIDC_ALLOW_UNVERIFIED_EMAIL = "true"
    OAUTH2_PROXY_EMAIL_DOMAINS                        = "*"
    OAUTH2_PROXY_COOKIE_REFRESH                       = "30m"
    OAUTH2_PROXY_COOKIE_EXPIRE                        = "8h"
    OAUTH2_PROXY_API_ROUTES                           = "^/(run|run_sse|apps/|list-apps|agui|agents/state|chat/api/|connections/|me\\b|threads\\b)"
    OAUTH2_PROXY_REDIRECT_URL                         = "https://${local.app_host}/oauth2/callback"
    OAUTH2_PROXY_COOKIE_SECURE                        = "true"
    OAUTH2_PROXY_REVERSE_PROXY                        = "true" # Cloud Run's front end sets X-Forwarded-*
    OAUTH2_PROXY_WHITELIST_DOMAINS                    = local.app_host
  }

  agent_env = merge(local.vertex_env, local.agent_entra_env, local.trace_env, {
    SDLC_MCP_URL     = "https://${local.mcp_host}/mcp"
    SDLC_AGENT_MODEL = var.agent_model
    # 0.0.0.0, not 127.0.0.1: Cloud Run's startup probes do not connect over loopback. Still private:
    # only the ingress container's port (oauth2-proxy, 4180) is exposed by a multi-container service.
    HOST            = "0.0.0.0"
    SDLC_AGUI_AGENT = "user_agent" # AG-UI endpoint /agui for the CopilotKit app (version-01 M5)
    # oauth2-proxy does not pass the browser's Host (PASS_HOST_HEADER=false), so ADK's cross-origin
    # guard needs the public origin explicitly, or the dev UI's scripts get 403.
    SDLC_ALLOWED_ORIGINS = "https://${local.app_host}"
    # Conversations in Agent Engine sessions (sessions.tf), deleted this many days after they start.
    SDLC_SESSION_SERVICE_URI    = "agentengine://${google_vertex_ai_reasoning_engine.sessions.id}"
    SDLC_SESSION_RETENTION_DAYS = tostring(var.session_retention_days)
  })

  # CopilotKit chat app sidecar (version-01 M5): forwards only the proxy's token header to /agui.
  ui_env = {
    SDLC_AGUI_URL                 = "http://127.0.0.1:8000/agui"
    HOSTNAME                      = "0.0.0.0" # probes need it; only port 4180 is exposed (see agent_env)
    PORT                          = "3000"
    NEXT_TELEMETRY_DISABLED       = "1"
    COPILOTKIT_TELEMETRY_DISABLED = "true"
    DO_NOT_TRACK                  = "1"
  }

  jobs_db_env = {
    PGHOST     = local.cloudsql_socket
    PGDATABASE = google_sql_database.sdlc.name
    PGUSER     = "sdlc_app"
  }
}

# --- MCP server ------------------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "mcp" {
  name                 = local.mcp_name
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = true
  deletion_protection  = var.deletion_protection

  template {
    service_account = google_service_account.w["mcp"].email
    # Cloud Storage volumes (config bundles) need the second generation execution environment.
    execution_environment = local.bundles ? "EXECUTION_ENVIRONMENT_GEN2" : null
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
    containers {
      image = local.images.mcp
      ports {
        container_port = 8080
      }
      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }
      dynamic "env" {
        for_each = local.mcp_env
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = local.mcp_secret_env
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
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      dynamic "volume_mounts" {
        for_each = local.bundles ? [] : [1]
        content {
          name       = "groups"
          mount_path = local.config_env_dir
        }
      }
      dynamic "volume_mounts" {
        for_each = local.users_secret ? [1] : []
        content {
          name       = "users"
          mount_path = local.users_dir
        }
      }
      dynamic "volume_mounts" {
        for_each = local.bundles ? [1] : []
        content {
          name       = "config-bundles"
          mount_path = local.bundles_dir
        }
      }
      startup_probe {
        http_get {
          path = "/healthz"
        }
        period_seconds    = 5
        failure_threshold = 12
      }
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.sdlc.connection_name]
      }
    }
    dynamic "volumes" {
      for_each = local.bundles ? [] : [1]
      content {
        name = "groups"
        secret {
          secret = local.secret["groups-yaml"]
          items {
            version = "latest"
            path    = "groups.yaml"
          }
        }
      }
    }
    dynamic "volumes" {
      for_each = local.users_secret ? [1] : []
      content {
        name = "users"
        secret {
          secret = local.secret["users-yaml"]
          items {
            version = "latest"
            path    = "users.yaml"
          }
        }
      }
    }
    dynamic "volumes" {
      for_each = local.bundles ? [1] : []
      content {
        name = "config-bundles"
        gcs {
          bucket        = google_storage_bucket.config_store[0].name
          read_only     = true
          mount_options = ["only-dir=bundles/${var.env}"]
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_version.s, google_secret_manager_secret_iam_member.w]
}

# --- agent UI: oauth2-proxy (ingress) + agent (sidecar) ------------------------------------------------

resource "google_cloud_run_v2_service" "app" {
  name                 = local.app_name
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = true
  deletion_protection  = var.deletion_protection

  template {
    service_account                  = google_service_account.w["app"].email
    timeout                          = "3600s" # streamed agent responses
    session_affinity                 = true
    max_instance_request_concurrency = 40
    scaling {
      min_instance_count = 0
      max_instance_count = var.app_max_instances
    }

    containers {
      name       = "oauth2-proxy"
      image      = local.images.oauth2_proxy
      depends_on = ["agent", "ui"]
      ports {
        container_port = 4180
      }
      resources {
        limits = { cpu = "1", memory = "256Mi" }
      }
      dynamic "env" {
        for_each = local.oauth2_proxy_env
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "OAUTH2_PROXY_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = local.secret["entra-client-secret"]
            version = "latest"
          }
        }
      }
      env {
        name = "OAUTH2_PROXY_COOKIE_SECRET"
        value_source {
          secret_key_ref {
            secret  = local.secret["oauth2-cookie"]
            version = "latest"
          }
        }
      }
    }

    containers {
      name  = "agent"
      image = local.images.agent
      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }
      dynamic "env" {
        for_each = local.agent_env
        content {
          name  = env.key
          value = env.value
        }
      }
      startup_probe {
        http_get {
          path = "/healthz"
          port = 8000
        }
        period_seconds    = 5
        failure_threshold = 24
      }
    }

    containers {
      name  = "ui"
      image = local.images.ui
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
      dynamic "env" {
        for_each = local.ui_env
        content {
          name  = env.key
          value = env.value
        }
      }
      startup_probe {
        http_get {
          path = "/chat/api/healthz"
          port = 3000
        }
        period_seconds    = 5
        failure_threshold = 24
      }
    }
  }

  depends_on = [google_secret_manager_secret_version.s, google_secret_manager_secret_iam_member.w]
}

# --- jobs ----------------------------------------------------------------------------------------

resource "google_cloud_run_v2_job" "db_setup" {
  name                = "sdlc-db-setup-${var.env}"
  location            = var.region
  deletion_protection = var.deletion_protection

  template {
    template {
      service_account = google_service_account.w["jobs"].email
      max_retries     = 0
      timeout         = "600s"
      containers {
        image   = local.images.ingest
        command = ["sh", "-c"]
        args    = ["sdlc-db bootstrap && sdlc-db migrate"]
        dynamic "env" {
          for_each = local.jobs_db_env
          content {
            name  = env.key
            value = env.value
          }
        }
        dynamic "env" {
          for_each = {
            POSTGRES_SUPERUSER_PASSWORD = "pg-admin-password"
            SDLC_OWNER_PASSWORD         = "pg-owner-password"
            PGPASSWORD                  = "pg-app-password"
            SDLC_INGEST_PASSWORD        = "pg-ingest-password"
          }
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
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.sdlc.connection_name]
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_version.s, google_secret_manager_secret_iam_member.w]
}

resource "google_cloud_run_v2_job" "ingest" {
  name                = "sdlc-ingest-${var.env}"
  location            = var.region
  deletion_protection = var.deletion_protection

  template {
    template {
      service_account = google_service_account.w["jobs"].email
      max_retries     = 0
      timeout         = "1800s"
      # Cloud Storage volumes (config bundles) need the second generation execution environment.
      execution_environment = local.bundles ? "EXECUTION_ENVIRONMENT_GEN2" : null
      containers {
        image = local.images.ingest
        args  = ["run", "--all"]
        resources {
          limits = { cpu = "1", memory = "1Gi" }
        }
        dynamic "env" {
          # Source credentials (spec.credentials {secret: x}) come from Secret Manager at run time
          # (version-01 M0); the jobs service account needs accessor on each connector secret.
          # With bundles, relative local_folder locations resolve against the image (/app).
          for_each = merge(local.vertex_env, local.entra_env, local.jobs_db_env, local.bundles_env, {
            SDLC_ENV             = var.env
            SDLC_SECRETS_BACKEND = "gcp"
            SDLC_SECRETS_PROJECT = var.project_id
            SDLC_SOURCES_ROOT    = "/app"
          })
          content {
            name  = env.key
            value = env.value
          }
        }
        env {
          name = "SDLC_INGEST_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = local.secret["pg-ingest-password"]
              version = "latest"
            }
          }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        dynamic "volume_mounts" {
          for_each = local.bundles ? [] : [1]
          content {
            name       = "groups"
            mount_path = local.config_env_dir
          }
        }
        dynamic "volume_mounts" {
          for_each = local.bundles ? [1] : []
          content {
            name       = "config-bundles"
            mount_path = local.bundles_dir
          }
        }
      }
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.sdlc.connection_name]
        }
      }
      dynamic "volumes" {
        for_each = local.bundles ? [] : [1]
        content {
          name = "groups"
          secret {
            secret = local.secret["groups-yaml"]
            items {
              version = "latest"
              path    = "groups.yaml"
            }
          }
        }
      }
      dynamic "volumes" {
        for_each = local.bundles ? [1] : []
        content {
          name = "config-bundles"
          gcs {
            bucket        = google_storage_bucket.config_store[0].name
            read_only     = true
            mount_options = ["only-dir=bundles/${var.env}"]
          }
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_version.s, google_secret_manager_secret_iam_member.w]
}

# User-connection reconcile (version-02 N3): deletes stored PATs of blocked users, expired and
# long-rejected tokens, and connections no longer configured (sdlc_connectors.reconcile). MCP image,
# own service account (iam.tf: name-prefixed user secrets + list), DB only for the per-user lock.
# Scheduled with reconcile_schedule (schedules.tf); by hand:
#   gcloud run jobs execute sdlc-reconcile-<env> --region <region> --args=--dry-run   (report only)
resource "google_cloud_run_v2_job" "reconcile" {
  name                = "sdlc-reconcile-${var.env}"
  location            = var.region
  deletion_protection = var.deletion_protection

  template {
    template {
      service_account       = google_service_account.w["reconcile"].email
      max_retries           = 0
      timeout               = "600s"
      execution_environment = local.bundles ? "EXECUTION_ENVIRONMENT_GEN2" : null
      containers {
        image   = local.images.mcp
        command = ["sdlc-reconcile-connections"]
        args    = ["--apply"]
        dynamic "env" {
          for_each = merge(local.vertex_env, local.entra_env, local.jobs_db_env, local.bundles_env, {
            SDLC_ENV                  = var.env
            SDLC_CONFIG_WATCH         = "false"
            SDLC_USER_SECRETS_BACKEND = "gcp"
            SDLC_SECRETS_PROJECT      = var.project_id
          })
          content {
            name  = env.key
            value = env.value
          }
        }
        env {
          name = "PGPASSWORD"
          value_source {
            secret_key_ref {
              secret  = local.secret["pg-app-password"]
              version = "latest"
            }
          }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        dynamic "volume_mounts" {
          for_each = local.bundles ? [] : [1]
          content {
            name       = "groups"
            mount_path = local.config_env_dir
          }
        }
        dynamic "volume_mounts" {
          for_each = local.bundles ? [1] : []
          content {
            name       = "config-bundles"
            mount_path = local.bundles_dir
          }
        }
      }
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.sdlc.connection_name]
        }
      }
      dynamic "volumes" {
        for_each = local.bundles ? [] : [1]
        content {
          name = "groups"
          secret {
            secret = local.secret["groups-yaml"]
            items {
              version = "latest"
              path    = "groups.yaml"
            }
          }
        }
      }
      dynamic "volumes" {
        for_each = local.bundles ? [1] : []
        content {
          name = "config-bundles"
          gcs {
            bucket        = google_storage_bucket.config_store[0].name
            read_only     = true
            mount_options = ["only-dir=bundles/${var.env}"]
          }
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_version.s, google_secret_manager_secret_iam_member.w]
}
