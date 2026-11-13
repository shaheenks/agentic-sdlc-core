output "app_url" {
  description = "Sign-in URL (oauth2-proxy -> agent)."
  value       = "https://${local.app_host}"
}

output "oauth_callback" {
  description = "Redirect URI to register on the Entra client app (sdlc-client)."
  value       = "https://${local.app_host}/oauth2/callback"
}

output "mcp_url" {
  value = "https://${local.mcp_host}/mcp"
}

output "mcp_native_url" {
  description = "MCP server with invoker IAM (CH-0013); empty unless native_enabled."
  value       = var.native_enabled ? "https://${local.mcp_native_host}/mcp" : ""
}

output "session_engine" {
  description = "Agent Engine that stores agent conversations."
  value       = google_vertex_ai_reasoning_engine.sessions.id
}

output "registry" {
  value = local.registry
}

output "sql_connection_name" {
  value = google_sql_database_instance.sdlc.connection_name
}

output "jobs" {
  value = {
    db_setup = google_cloud_run_v2_job.db_setup.name
    ingest   = google_cloud_run_v2_job.ingest.name
  }
}

output "config_store_bucket" {
  description = "Content bucket for gcs sources (empty when not created)."
  value       = var.config_store_bucket == "" ? "" : "gs://${google_storage_bucket.config_store[0].name}"
}

output "artifact_store_bucket" {
  description = "Bucket for temporary files and agent artefacts (empty when not created)."
  value       = var.artifact_store_bucket == "" ? "" : "gs://${google_storage_bucket.artifact_store[0].name}"
}

output "agent_gateway" {
  description = "Agent Gateway for the engine's outbound traffic (scripts/deploy_agent_runtime.py); empty when off."
  value       = local.gateway_on ? google_network_services_agent_gateway.egress[0].id : ""
}
