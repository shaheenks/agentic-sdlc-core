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
