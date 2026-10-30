variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "env" {
  description = "Environment name: SDLC_ENV, config/env/<env>/, resource name suffix."
  type        = string
}

variable "image_tag" {
  description = "Tag of the sdlc images in Artifact Registry (scripts/gcp_deploy.ps1: git short SHA)."
  type        = string
}

variable "oauth2_proxy_tag" {
  description = "Mirrored quay.io/oauth2-proxy/oauth2-proxy tag (Cloud Run cannot pull from quay.io)."
  type        = string
  default     = "v7.15.4-alpine"
}

# Tenant-specific values: passed from .env as TF_VAR_* by scripts/gcp_deploy.ps1, never committed.
variable "entra_tenant_id" {
  type = string
}

variable "entra_authority_host" {
  description = "Entra login host (E7: sovereign clouds); keep in sync with platform.yaml."
  type        = string
  default     = "https://login.microsoftonline.com"
}

variable "entra_api_client_id" {
  description = "sdlc-mcp app registration (token audience)."
  type        = string
}

variable "entra_client_id" {
  description = "sdlc-client app registration (oauth2-proxy)."
  type        = string
}

variable "entra_client_secret" {
  type      = string
  sensitive = true
}

variable "entra_graph_client_secret" {
  description = "Optional: Graph fallback for group overage. Empty = no fallback (fail closed)."
  type        = string
  sensitive   = true
  default     = ""
}

variable "groups_yaml_path" {
  description = "Git-ignored GroupMap for this env (tenant group IDs), stored in Secret Manager."
  type        = string
}

variable "agent_model" {
  type    = string
  default = "gemini-3.8-flash"
}

variable "vertex_location" {
  type    = string
  default = "global"
}

variable "sql_tier" {
  type    = string
  default = "db-g1-small"
}

variable "deletion_protection" {
  description = "Protect Cloud SQL and Cloud Run from terraform destroy."
  type        = bool
  default     = true
}

variable "app_max_instances" {
  description = "sdlc-app instances. Conversations live in Agent Engine sessions (sessions.tf), so more than 1 is possible; raise it after checking a conversation survives a new revision."
  type        = number
  default     = 1
}

variable "session_retention_days" {
  description = "Agent conversations (Agent Engine sessions) are deleted this many days after they start."
  type        = number
  default     = 7
}

variable "gcs_source_buckets" {
  description = "Buckets read by `gcs` sources (config/sources). The ingest job gets objectViewer on these buckets only (version-01 M2)."
  type        = list(string)
  default     = []
}
