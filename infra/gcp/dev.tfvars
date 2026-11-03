# Environment "dev" on GCP (version-01 M7). Tenant values come from .env via scripts/gcp_deploy.ps1.
project_id            = "sdlc-demo-env01"
region                = "asia-southeast1"
env                   = "dev"
groups_yaml_path      = "../../config/env/dev/groups.yaml"
sql_tier              = "db-g1-small"
deletion_protection   = false                          # dev environment with synthetic data: allow terraform destroy
config_store_bucket   = "sdlc-config-store-a7484d8b"   # source content for ingest (storage.tf)
artifact_store_bucket = "sdlc-artifact-store-a7484d8b" # temporary files and agent artefacts (storage.tf)
