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

# Outbound internet for the services whose egress goes through the VPC (user_agent_mcp: all traffic, so that it
# reaches Knowledge Search on internal ingress). The connectors call GitHub, Bitbucket, Jira and Confluence on the
# public internet (phase 4); without NAT the VPC has no route there. Addresses are allocated automatically.
resource "google_compute_router" "platform" {
  name    = "${local.prefix}-${var.region}"
  network = google_compute_network.platform.id
  region  = var.region
}

resource "google_compute_router_nat" "platform" {
  name                               = "${local.prefix}-${var.region}"
  router                             = google_compute_router.platform.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.platform.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
