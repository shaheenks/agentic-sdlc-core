# Agent Registry and Agent Gateway for the native stack (design D17, CH-0015, NFR-SEC-015).
#
# The user agent on Agent Runtime sends all its outbound traffic through a Google-managed Agent
# Gateway (AGENT_TO_ANYWHERE). The gateway asks IAP to authorize each request: the agent's identity
# needs roles/iap.egressor on the registered MCP server, and only for the tools config declares
# (generated/gateway_policy.json, from `sdlc-config gateway-policy`; a test keeps it equal to
# config). Per-user access is still decided by the MCP server from the user's Entra token.
#
# Rollout: agent_gateway_enabled creates everything with the IAP check in DRY_RUN (decisions are
# logged, nothing is blocked). Set agent_gateway_enforce = true once the logs show the expected
# allows and denies. The engine is attached by scripts/deploy_agent_runtime.py
# (terraform output agent_gateway).

locals {
  gateway_on     = var.native_enabled && var.agent_gateway_enabled
  gateway_policy = jsondecode(file("${path.module}/generated/gateway_policy.json"))
  # MCP handshake calls (initialize, tools/list) carry no tool name, so "" must be allowed too.
  gateway_tool_condition = format(
    "api.getAttribute('iap.googleapis.com/mcp.toolName', '') in [%s]",
    join(", ", formatlist("'%s'", concat(local.gateway_policy.tools, [""]))),
  )
}

resource "google_network_services_agent_gateway" "egress" {
  count       = local.gateway_on ? 1 : 0
  name        = "sdlc-agents-${var.env}"
  location    = var.region
  description = "Egress for agents on Agent Runtime: only registered destinations, tools from config"
  protocols   = ["MCP"]
  registries  = ["//agentregistry.googleapis.com/projects/${var.project_id}/locations/${var.region}"]
  google_managed {
    governed_access_path = "AGENT_TO_ANYWHERE"
  }
  depends_on = [google_project_service.apis]
}

# sdlc-mcp-native as a registered destination, with its tools (the gateway reads tool names from it).
resource "google_agent_registry_service" "mcp_native" {
  count        = local.gateway_on ? 1 : 0
  service_id   = "sdlc-mcp-native"
  location     = var.region
  display_name = "SDLC core MCP server (native)"
  description  = "core_mcp on Cloud Run, invoker IAM on; per-user access by the Entra token"
  interfaces {
    url              = "https://${local.mcp_native_host}/mcp"
    protocol_binding = "JSONRPC"
  }
  mcp_server_spec {
    type    = "TOOL_SPEC"
    content = jsonencode(local.gateway_policy.toolspec)
  }
}

resource "google_network_services_authz_extension" "iap" {
  count     = local.gateway_on ? 1 : 0
  name      = "sdlc-agents-${var.env}-iap"
  location  = var.region
  service   = "iap.googleapis.com"
  timeout   = "1s"
  fail_open = !var.agent_gateway_enforce # DRY_RUN: log, never block
  metadata  = var.agent_gateway_enforce ? {} : { iamEnforcementMode = "DRY_RUN" }
}

resource "google_network_security_authz_policy" "gateway" {
  count          = local.gateway_on ? 1 : 0
  name           = "sdlc-agents-${var.env}-authz"
  location       = var.region
  action         = "CUSTOM"
  policy_profile = "REQUEST_AUTHZ"
  target {
    resources = [google_network_services_agent_gateway.egress[0].id]
  }
  custom_provider {
    authz_extension {
      resources = [google_network_services_authz_extension.iap[0].id]
    }
  }
}

# The user agent may reach sdlc-mcp-native through the gateway, for the configured tools only.
resource "google_iap_agent_registry_mcp_server_iam_member" "agent" {
  count         = local.gateway_on && var.agent_runtime_principal != "" ? 1 : 0
  project       = var.project_id
  location      = var.region
  mcp_server_id = basename(google_agent_registry_service.mcp_native[0].registry_resource)
  role          = "roles/iap.egressor"
  member        = var.agent_runtime_principal
  condition {
    title       = "Tools declared in config"
    description = "generated/gateway_policy.json (sdlc-config gateway-policy), plus the MCP handshake"
    expression  = local.gateway_tool_condition
  }
}
