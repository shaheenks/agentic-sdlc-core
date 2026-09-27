terraform {
  required_version = ">= 1.9"
  required_providers {
    google = { source = "hashicorp/google", version = ">= 6.20, < 8.0" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
  # bucket + prefix come from <env>.gcs.tfbackend (terraform init -backend-config=...)
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}
