# Conversation store for the agent (version-01 M8): Vertex AI Agent Engine sessions.
# The engine holds sessions only (no deployed code, no memory bank). The agent reaches it with the
# app service account (roles/aiplatform.user, iam.tf); sdlc_web sets a TTL of
# var.session_retention_days on every new session. Users only ever see their own sessions: the
# user id is the Entra oid and the agent's middleware checks every session route.

resource "google_vertex_ai_reasoning_engine" "sessions" {
  project      = var.project_id
  region       = var.region
  display_name = "sdlc-sessions-${var.env}"
  description  = "Agent conversations (sdlc-app-${var.env}); sessions only, no deployed agent"
  labels       = { env = var.env, purpose = "agent-sessions" }

  depends_on = [google_project_service.apis]
}
