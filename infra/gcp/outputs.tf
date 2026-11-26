output "service_accounts" {
  description = "Service account email per component."
  value       = { for k, sa in google_service_account.component : k => sa.email }
}

output "config_bucket" {
  value = google_storage_bucket.config.name
}

output "artifact_bucket" {
  value = google_storage_bucket.artifacts.name
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "subnet" {
  value = google_compute_subnetwork.platform.id
}

output "user_agent_mcp_url" {
  value = local.user_agent_mcp_url
}

output "knowledge_bucket" {
  value = google_storage_bucket.knowledge.name
}

output "knowledge_search_url" {
  value = local.knowledge_search_url
}

output "knowledge_ingest_service_account" {
  value = google_service_account.component["knowledge_ingest"].email
}

output "project_id" {
  value = var.project_id
}

output "interactive_agents_service_account" {
  value = google_service_account.component["interactive_agents"].email
}

output "sdlc_ui_url" {
  value = local.sdlc_ui_url
}

output "event_agents_service_account" {
  value = google_service_account.component["event_agents"].email
}

output "event_agent_mcp_url" {
  value = local.event_agent_mcp_url
}

output "event_gateway_webhook_url" {
  description = "The URL of GitHub's webhook on a control repository (content type application/json)."
  value       = "${local.event_gateway_url}/webhooks/github"
}

output "code_workspace_job" {
  value = local.code_workspace_job
}

output "webhook_secret_github" {
  description = "The Secret Manager secret holding the GitHub webhook's secret."
  value       = google_secret_manager_secret.platform["webhook-github"].secret_id
}

output "system_pat_github" {
  description = "The Secret Manager secret holding the GitHub machine user's token."
  value       = google_secret_manager_secret.platform["system-pat-github"].secret_id
}
