# Shared VPC for platform services (sample)
resource "google_compute_network" "platform" {
  name                    = "platform-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "services" {
  name          = "services"
  network       = google_compute_network.platform.id
  ip_cidr_range = "10.20.0.0/20"
  region        = "asia-south1"
}
