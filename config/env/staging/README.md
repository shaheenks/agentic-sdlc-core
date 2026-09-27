# staging (GCP, Stage 7)

Same Entra tenant as local/dev. `groups.yaml` (git-ignored) is uploaded to Secret Manager by
`scripts/gcp_deploy.ps1` and mounted at `/app/config/env/staging/groups.yaml` on Cloud Run.
Create it from `../local/groups.yaml.example` (or copy the local one for the same tenant).
