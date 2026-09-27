# Cloud SQL for PostgreSQL + pgvector. Reached only through the Cloud SQL connector (Cloud Run's
# /cloudsql socket): public IP for the connector, no authorized networks (org policy enforces it).
# Roles, schema and RLS are created by the sdlc-db-setup job (sdlc-db bootstrap + migrate).

resource "google_sql_database_instance" "sdlc" {
  name                = "sdlc-${var.env}"
  database_version    = "POSTGRES_17"
  region              = var.region
  deletion_protection = var.deletion_protection

  settings {
    edition           = "ENTERPRISE"
    tier              = var.sql_tier
    availability_type = "ZONAL"
    disk_size         = 10
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled = true
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "sdlc" {
  name     = "sdlc"
  instance = google_sql_database_instance.sdlc.name
}

# Built-in admin user (cloudsqlsuperuser, not a true superuser): used only by sdlc-db bootstrap.
resource "google_sql_user" "admin" {
  name     = "postgres"
  instance = google_sql_database_instance.sdlc.name
  password = random_password.db["admin"].result
}
