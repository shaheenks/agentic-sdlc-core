# Secret Manager: generated DB passwords + cookie secret, and tenant values from .env and the
# git-ignored (optional) users.yaml. No group map or Graph secret since CH-0011/CH-0012. Values are also in the Terraform state (GCS bucket, restricted).

resource "random_password" "db" {
  for_each = toset(["admin", "owner", "app", "ingest"])
  length   = 32
  special  = false
}

resource "random_password" "cookie" {
  length  = 32 # oauth2-proxy needs a 16/24/32-byte cookie secret
  special = false
}

locals {
  secret_values = merge(
    {
      "pg-admin-password"   = random_password.db["admin"].result
      "pg-owner-password"   = random_password.db["owner"].result
      "pg-app-password"     = random_password.db["app"].result
      "pg-ingest-password"  = random_password.db["ingest"].result
      "oauth2-cookie"       = random_password.cookie.result
      "entra-client-secret" = var.entra_client_secret
    },
    local.users_secret ? { # with config bundles, users.yaml travels in the bundle instead
      "users-yaml" = file(var.users_yaml_path)
    } : {},
    local.ui_native_on ? { # the native chat UI (CH-0016): the Web OAuth client secret, the cookie key
      "google-web-client-secret" = var.google_web_client_secret
      "ui-session-key"           = random_id.ui_session_key[0].b64_url
    } : {},
  )
}

resource "google_secret_manager_secret" "s" {
  for_each  = nonsensitive(toset(keys(local.secret_values)))
  secret_id = "sdlc-${var.env}-${each.value}"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "s" {
  for_each    = google_secret_manager_secret.s
  secret      = each.value.id
  secret_data = local.secret_values[each.key]
}
