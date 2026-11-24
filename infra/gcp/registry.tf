# Container images of every Cloud Run service and job (NFR-OPS-001).
resource "google_artifact_registry_repository" "images" {
  repository_id = local.prefix
  location      = var.region
  format        = "DOCKER"
  description   = "Images of the agentic SDLC platform (${var.env})."
  depends_on    = [google_project_service.apis]
}
