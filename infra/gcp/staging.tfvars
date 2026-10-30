# Environment "staging" (Stage 7a). Tenant values come from .env via scripts/gcp_deploy.ps1.
project_id          = "sdlc-demo-env01"
region              = "asia-southeast1"
env                 = "staging"
groups_yaml_path    = "../../config/env/staging/groups.yaml"
sql_tier            = "db-g1-small"
deletion_protection = false # test environment with synthetic data: allow terraform destroy
