locals {
  prefix = "sdlc-${var.env}"

  apis = [
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iap.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
  ]

  # One service account per component (NFR-SEC-006). Keys are component names; values are account ids.
  components = {
    sdlc_ui            = "${local.prefix}-sdlc-ui"
    a2a_router         = "${local.prefix}-a2a-router"
    user_agent_mcp     = "${local.prefix}-user-agent-mcp"
    event_agent_mcp    = "${local.prefix}-event-agent-mcp"
    interactive_agents = "${local.prefix}-interactive-agents"
    event_agents       = "${local.prefix}-event-agents"
    knowledge_search   = "${local.prefix}-knowledge-search"
    knowledge_ingest   = "${local.prefix}-knowledge-ingest"
    event_gateway      = "${local.prefix}-event-gateway"
    code_workspace     = "${local.prefix}-code-workspace"
    code_workspace_usr = "${local.prefix}-code-workspace-usr" # the credential-free user job (DEC-0016)
  }
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}
