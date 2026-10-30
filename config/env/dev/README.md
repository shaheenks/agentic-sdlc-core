# dev (GCP project sdlc-demo-env01, asia-southeast1; version-01 M7)

Same Entra tenant as local. `groups.yaml` (git-ignored) is uploaded to Secret Manager by
`scripts/gcp_deploy.ps1` and mounted at `/app/config/env/dev/groups.yaml` on Cloud Run.
Create it from `../local/groups.yaml.example`, or copy `../local/groups.yaml` for the same tenant:

    Copy-Item config/env/local/groups.yaml config/env/dev/groups.yaml
