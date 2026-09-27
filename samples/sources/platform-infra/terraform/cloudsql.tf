# Cloud SQL instances for product teams (sample)
resource "google_sql_database_instance" "ledger_db" {
  name             = "ledger-db"
  database_version = "POSTGRES_17"
  region           = "asia-south1"

  settings {
    tier              = "db-custom-4-16384"
    availability_type = "REGIONAL" # automatic failover to the standby zone
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }
  }
}

resource "google_sql_database_instance" "payments_db" {
  name             = "payments-db"
  database_version = "POSTGRES_17"
  region           = "asia-south1"
}
