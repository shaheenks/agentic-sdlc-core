# dev (GCP project sdlc-demo-env01, asia-southeast1; version-01 M7)

Same Entra tenant as local. Membership comes from Entra app roles (CH-0011); the optional,
git-ignored `users.yaml` adds direct members and travels in the config bundle.

`groups.yaml` is no longer read. `gcp_deploy.ps1 -Step plan` still needs the file because
Terraform creates the unused `groups-yaml` secret from it, until infra/gcp drops that secret.
