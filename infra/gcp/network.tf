# Network for Direct VPC egress, so services can reach internal-only ingress (knowledge_search,
# user_agent_mcp, event_agent_mcp). The Agent Runtime network attachment is added in phase 5.
resource "google_compute_network" "platform" {
  name                    = local.prefix
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "platform" {
  name                     = "${local.prefix}-${var.region}"
  network                  = google_compute_network.platform.id
  region                   = var.region
  ip_cidr_range            = var.subnet_cidr
  private_ip_google_access = true
}
