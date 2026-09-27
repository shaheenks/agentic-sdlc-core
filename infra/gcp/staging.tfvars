# Environment "staging" (Stage 7a). Tenant values come from .env via scripts/gcp_deploy.sh.
project_id          = "cloud-migration-agent"
region              = "asia-south1"
env                 = "staging"
groups_yaml_path    = "../../config/env/staging/groups.yaml"
sql_tier            = "db-g1-small"
deletion_protection = false # test environment with synthetic data: allow terraform destroy
