# GCP deployment of one environment (Stage 7a). See infra/README.md.

data "google_project" "this" {
  project_id = var.project_id
}

locals {
  services = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "iam.googleapis.com",
  ]

  # Cloud Run's deterministic URLs (https://<service>-<project number>.<region>.run.app), known
  # before the services exist, so each service can be configured with its own public URL.
  app_name = "sdlc-app-${var.env}"
  mcp_name = "sdlc-mcp-${var.env}"
  app_host = "${local.app_name}-${data.google_project.this.number}.${var.region}.run.app"
  mcp_host = "${local.mcp_name}-${data.google_project.this.number}.${var.region}.run.app"

  registry = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.sdlc.repository_id}"
  images = {
    mcp          = "${local.registry}/mcp-bootstrap:${var.image_tag}"
    agent        = "${local.registry}/agent-bootstrap:${var.image_tag}"
    ingest       = "${local.registry}/ingest:${var.image_tag}"
    oauth2_proxy = "${local.registry}/oauth2-proxy:${var.oauth2_proxy_tag}"
  }

  cloudsql_socket = "/cloudsql/${google_sql_database_instance.sdlc.connection_name}"
  config_env_dir  = "/app/config/env/${var.env}" # groups.yaml is mounted here from Secret Manager

  vertex_env = {
    GOOGLE_GENAI_USE_VERTEXAI = "TRUE"
    GOOGLE_CLOUD_PROJECT      = var.project_id
    GOOGLE_CLOUD_LOCATION     = var.vertex_location
  }
  entra_env = {
    ENTRA_TENANT_ID     = var.entra_tenant_id
    ENTRA_API_CLIENT_ID = var.entra_api_client_id
  }
  agent_entra_env = merge(local.entra_env, { ENTRA_AUTHORITY_HOST = var.entra_authority_host })
}

resource "google_project_service" "apis" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "sdlc" {
  repository_id = "sdlc"
  location      = var.region
  format        = "DOCKER"
  description   = "agentic-sdlc images (scripts/gcp_deploy.ps1)"
  depends_on    = [google_project_service.apis]
}
