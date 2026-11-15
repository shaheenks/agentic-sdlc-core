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
# allows and denies, and no request shows `unregisteredEndpoint` (CH-0018). The engine is attached
# by scripts/deploy_agent_runtime.py (terraform output agent_gateway).

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
  # V1 = IAP evaluates IAM allow bindings, which is how the agent's grant below is written (role +
  # tool-name condition). Google recommends V2 (Unified Access Policy); moving to it means
  # rewriting the grant as an IAM agent policy (follow-up).
  metadata = merge(
    { iapPolicyVersion = "V1" },
    var.agent_gateway_enforce ? {} : { iamEnforcementMode = "DRY_RUN" },
  )
  depends_on = [google_project_service.apis]
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
  depends_on = [google_project_service.apis]
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

# The agent's other destinations (CH-0018). With AGENT_TO_ANYWHERE egress, everything the agent
# calls goes through the gateway, and anything not registered is denied once enforced
# (unregisteredEndpoint). These are the destinations the DRY_RUN audit log showed besides the MCP
# server. No wildcard host and no unregistered-endpoint rule: each destination is named here.
locals {
  agent_egress = {
    # Google signing keys: the runtime app re-validates the user's Google ID token (CH-0014;
    # CH-0022 replaced the Entra keys: the engine serves the GCP stack).
    "google-signing-keys" = {
      url         = "https://www.googleapis.com/oauth2/v3/certs"
      description = "Google signing keys (JWKS) for user ID token validation"
    }
    # Gemini (SDLC_MODEL_LOCATION=global in scripts/deploy_agent_runtime.py).
    "vertex-ai-global" = {
      url         = "https://aiplatform.mtls.googleapis.com"
      description = "Gemini on Vertex AI (global endpoint)"
    }
    # Agent Runtime sessions, in the engine's region.
    "vertex-ai-regional" = {
      url         = "https://${var.region}-aiplatform.mtls.googleapis.com"
      description = "Agent Runtime sessions in the engine's region"
    }
  }
}

resource "google_agent_registry_service" "agent_egress" {
  for_each     = local.gateway_on ? local.agent_egress : {}
  service_id   = each.key
  location     = var.region
  display_name = each.key
  description  = each.value.description
  interfaces {
    url              = each.value.url
    protocol_binding = "HTTP_JSON"
  }
  endpoint_spec {
    type = "NO_SPEC"
  }
}

resource "google_iap_agent_registry_endpoint_iam_member" "agent_egress" {
  for_each    = var.agent_runtime_principal != "" ? google_agent_registry_service.agent_egress : {}
  project     = var.project_id
  location    = var.region
  endpoint_id = basename(each.value.registry_resource)
  role        = "roles/iap.egressor"
  member      = var.agent_runtime_principal
}
