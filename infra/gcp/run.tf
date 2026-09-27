# Cloud Run: sdlc-mcp (public; the Entra token is the gate), sdlc-app (oauth2-proxy ingress + agent
# sidecar on localhost) and the jobs sdlc-db-setup / sdlc-ingest.
# Public without an allUsers binding (org policy iam.allowedPolicyMemberDomains): invoker_iam_disabled.

locals {
  secret = { for k, v in google_secret_manager_secret.s : k => v.secret_id }

  mcp_env = merge(local.vertex_env, local.entra_env, {
    SDLC_ENV          = var.env
    SDLC_CONFIG_WATCH = "false" # config is baked into the image per release (bundles: 7b)
    MCP_PUBLIC_URL    = "https://${local.mcp_host}"
    PGHOST            = local.cloudsql_socket
    PGDATABASE        = google_sql_database.sdlc.name
    PGUSER            = "sdlc_app"
  })
  mcp_secret_env = merge(
    { PGPASSWORD = "pg-app-password" },
    contains(keys(local.secret), "entra-graph-secret") ? { ENTRA_GRAPH_CLIENT_SECRET = "entra-graph-secret" } : {},
  )

  # Same settings as the local oauth2-proxy (docker-compose.yml x-oauth2-proxy-env).
  oauth2_proxy_env = {
    OAUTH2_PROXY_PROVIDER                             = "oidc"
    OAUTH2_PROXY_PROVIDER_DISPLAY_NAME                = "Entra ID"
    OAUTH2_PROXY_OIDC_ISSUER_URL                      = "${var.entra_authority_host}/${var.entra_tenant_id}/v2.0"
    OAUTH2_PROXY_CLIENT_ID                            = var.entra_client_id
    OAUTH2_PROXY_SCOPE                                = "openid profile email offline_access api://${var.entra_api_client_id}/access_as_user"
    OAUTH2_PROXY_CODE_CHALLENGE_METHOD                = "S256"
    OAUTH2_PROXY_UPSTREAMS                            = "http://127.0.0.1:8000"
    OAUTH2_PROXY_HTTP_ADDRESS                         = "0.0.0.0:4180"
    OAUTH2_PROXY_PASS_ACCESS_TOKEN                    = "true"
    OAUTH2_PROXY_SKIP_PROVIDER_BUTTON                 = "true"
    OAUTH2_PROXY_OIDC_EMAIL_CLAIM                     = "preferred_username"
    OAUTH2_PROXY_SKIP_CLAIMS_FROM_PROFILE_URL         = "true"
    OAUTH2_PROXY_INSECURE_OIDC_ALLOW_UNVERIFIED_EMAIL = "true"
    OAUTH2_PROXY_EMAIL_DOMAINS                        = "*"
    OAUTH2_PROXY_COOKIE_REFRESH                       = "30m"
    OAUTH2_PROXY_COOKIE_EXPIRE                        = "8h"
    OAUTH2_PROXY_API_ROUTES                           = "^/(run|run_sse|apps/|list-apps)"
    OAUTH2_PROXY_REDIRECT_URL                         = "https://${local.app_host}/oauth2/callback"
    OAUTH2_PROXY_COOKIE_SECURE                        = "true"
    OAUTH2_PROXY_REVERSE_PROXY                        = "true" # Cloud Run's front end sets X-Forwarded-*
    OAUTH2_PROXY_WHITELIST_DOMAINS                    = local.app_host
  }

  agent_env = merge(local.vertex_env, local.agent_entra_env, {
    SDLC_MCP_URL     = "https://${local.mcp_host}/mcp"
    SDLC_AGENT_MODEL = var.agent_model
    HOST             = "127.0.0.1" # reachable only through oauth2-proxy in the same instance
  })

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
      volume_mounts {
        name       = "groups"
        mount_path = local.config_env_dir
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
    volumes {
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
      depends_on = ["agent"]
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
      containers {
        image = local.images.ingest
        args  = ["run", "--all"]
        resources {
          limits = { cpu = "1", memory = "1Gi" }
        }
        dynamic "env" {
          for_each = merge(local.vertex_env, local.entra_env, local.jobs_db_env, { SDLC_ENV = var.env })
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
        volume_mounts {
          name       = "groups"
          mount_path = local.config_env_dir
        }
      }
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.sdlc.connection_name]
        }
      }
      volumes {
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
  }

  depends_on = [google_secret_manager_secret_version.s, google_secret_manager_secret_iam_member.w]
}
