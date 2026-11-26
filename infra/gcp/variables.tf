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

variable "sdlc_ui_image" {
  description = "sdlc_ui's image. Empty: the service is not created yet."
  type        = string
  default     = ""
}

variable "agent_engine" {
  description = "user_agent's Agent Runtime resource: projects/<number>/locations/<region>/reasoningEngines/<id> (printed by interactive_agents/user_agent/deploy.py)."
  type        = string
  default     = ""
}

variable "sdlc_ui_users" {
  description = "Who may pass IAP to sdlc_ui (user:, group: or domain: members)."
  type        = list(string)
  default     = []
}

variable "iap_oauth_client_id" {
  description = "IAP's own OAuth client, for users outside the project's organisation. Empty: the Google-managed client."
  type        = string
  default     = ""
}

variable "iap_oauth_client_secret" {
  description = "The secret of iap_oauth_client_id (kept in state)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "event_agent_mcp_image" {
  description = "event_agent_mcp's image (DEC-0015). Empty: the service is not created yet."
  type        = string
  default     = ""
}

variable "event_agent_mcp_ingress" {
  description = "Cloud Run ingress of event_agent_mcp. The event agents' engine reaches it over its public URL, so ALL with the engine's account as its only invoker; internal once the engine has a private network path."
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "code_workspace_image" {
  description = "The Code Workspace job's image (DEC-0015). Empty: the job is not created yet."
  type        = string
  default     = ""
}

variable "event_gateway_image" {
  description = "event_gateway's image (DEC-0015). Empty: the service is not created yet."
  type        = string
  default     = ""
}

variable "event_agent_engine" {
  description = "The event agents' Agent Runtime resource: projects/<number>/locations/<region>/reasoningEngines/<id> (printed by event_based_agents/ci_workflow_agent/deploy.py). Empty: the gateway is not created yet."
  type        = string
  default     = ""
}
