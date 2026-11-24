variable "project_id" {
  description = "Google Cloud project of this environment."
  type        = string
}

variable "env" {
  description = "Environment name, used in resource names (for example dev)."
  type        = string
  default     = "dev"
}

variable "region" {
  description = "Region of every regional resource (NFR-HOST-005)."
  type        = string
  default     = "europe-west3"
}

variable "artifact_retention_days" {
  description = "Days after which objects under artifacts/ are deleted (FR-ART-003)."
  type        = number
  default     = 7
}

variable "subnet_cidr" {
  description = "Range of the platform subnet, used for Direct VPC egress to internal-only services."
  type        = string
  default     = "10.10.0.0/24"
}
