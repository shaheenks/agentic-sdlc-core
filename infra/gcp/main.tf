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
    "storage.googleapis.com",
    "cloudresourcemanager.googleapis.com", # data.google_project; enable once by hand before the first plan
    # version-02 N4: Cloud Trace (no cost while cloud_trace = false)
    "cloudtrace.googleapis.com",
  ]
  # GCP-native hosting (design D17, phase WN): APIs only, no resources. Enabled with
  # agent_platform_apis = true; they stay enabled when it is switched off again.
  agent_platform_services = [
    "iap.googleapis.com",                      # IAP on Cloud Run (UI sign-in)
    "agentregistry.googleapis.com",            # Agent Registry (preview)
    "agentidentity.googleapis.com",            # Agent Identity (SPIFFE principal per agent)
    "agentidentitycredentials.googleapis.com", # credentials for agent identities
    "networkservices.googleapis.com",          # Agent Gateway
    "networksecurity.googleapis.com",          # authorization policy on the gateway (CH-0015)
    "modelarmor.googleapis.com",               # optional prompt and response screening
  ]

  # Cloud Run's deterministic URLs (https://<service>-<project number>.<region>.run.app), known
  # before the services exist, so each service can be configured with its own public URL.
  app_name = "sdlc-app-${var.env}"
  mcp_name = "sdlc-mcp-${var.env}"
  app_host = "${local.app_name}-${data.google_project.this.number}.${var.region}.run.app"
  mcp_host = "${local.mcp_name}-${data.google_project.this.number}.${var.region}.run.app"
  # GCP-native hosting (design D17, CH-0013): a second MCP service that only allowed Google identities
  # can invoke (Cloud Run IAM). Since CH-0022 it is the GCP stack's server, core_mcp_gcp: the user's
  # Google ID token and Google groups decide per-user access, as its own service account (the only
  # one with Groups Reader). `main` stays the Entra stack's core_mcp.
  mcp_native_name = "sdlc-mcp-native"
  mcp_native_host = "${local.mcp_native_name}-${data.google_project.this.number}.${var.region}.run.app"
  mcp_services = merge(
    { main = { name = local.mcp_name, host = local.mcp_host, public = true, workload = "mcp", image = "mcp", idp = "entra" } },
    var.native_enabled ? { native = { name = local.mcp_native_name, host = local.mcp_native_host, public = false, workload = "mcp-gcp", image = "mcp_gcp", idp = "google" } } : {},
  )

  registry = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.sdlc.repository_id}"
  images = {
    # One tag per image, from its own build inputs (CH-0024, scripts/build_tag.py): an unchanged
    # image keeps its reference, so its services get no new revision.
    mcp          = "${local.registry}/core-mcp:${var.image_tags["mcp"]}"
    mcp_gcp      = "${local.registry}/core-mcp-gcp:${var.image_tags["mcp_gcp"]}" # GCP stack (CH-0022)
    agent        = "${local.registry}/user-agent:${var.image_tags["agent"]}"
    ingest       = "${local.registry}/ingest:${var.image_tags["ingest"]}"
    ui           = "${local.registry}/ui-copilotkit:${var.image_tags["ui"]}" # CopilotKit chat app (version-01 M5)
    oauth2_proxy = "${local.registry}/oauth2-proxy:${var.oauth2_proxy_tag}"
  }

  cloudsql_socket = "/cloudsql/${google_sql_database_instance.sdlc.connection_name}"
  # users.yaml (optional) gets its own folder: Cloud Run mounts one secret per folder.
  users_dir = "/app/config-users"

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

  # Cloud Trace (version-02 N4): agent and MCP export spans with their service identity. Same span
  # rules as locally (no prompts, tokens or argument values); one agent turn = one trace.
  trace_env = var.cloud_trace ? { SDLC_TRACE_TO_CLOUD = "true" } : {}
}

resource "google_project_service" "apis" {
  for_each = toset(concat(
    local.services,
    var.agent_platform_apis ? local.agent_platform_services : [],
    # Cloud Identity Groups API: Google group membership for core_mcp_gcp (CH-0021, CH-0022)
    var.native_enabled ? ["cloudidentity.googleapis.com"] : [],
  ))
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
