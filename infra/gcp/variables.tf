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

variable "user_agent_mcp_image" {
  description = "Image of user_agent_mcp, tagged with the commit it was built from."
  type        = string
}

variable "user_agent_mcp_ingress" {
  description = "Cloud Run ingress of user_agent_mcp: INGRESS_TRAFFIC_ALL until sdlc_ui runs here, then INGRESS_TRAFFIC_INTERNAL_ONLY."
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "sdlc_ui_url" {
  description = "sdlc_ui's URL, for connection_start links; empty until sdlc_ui is deployed."
  type        = string
  default     = ""
}

variable "sdlc_ui_testers" {
  description = "Development only: members (user:<email>) who may impersonate sdlc_ui's service account to call user_agent_mcp. Set in the git-ignored <env>.tfvars."
  type        = list(string)
  default     = []
}
variable "knowledge_search_image" {
  description = "First image of knowledge_search (built by knowledge_ingest/cloudbuild.yaml). Empty: the service, and user_agent_mcp's knowledge settings, are not created yet. Later refreshes roll out their own images."
  type        = string
  default     = ""
}

variable "knowledge_refreshers" {
  description = "Members (user:, group:) who may run the knowledge refresh as the knowledge_ingest service account."
  type        = list(string)
  default     = []
}
