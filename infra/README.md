# infra

Terraform for the Google Cloud environments ([GCP Foundation](../spec/components/gcp-foundation.md)).
Only the development environment exists for now.

`gcp/` defines, per environment: the APIs, one service account per component, the configuration and artifact
buckets (with per-MCP-server prefix conditions), Secret Manager secret containers (values are added by hand),
the Artifact Registry repository and the network for internal-only services.

```sh
cd infra/gcp
cp dev.tfvars.example dev.tfvars                 # fill in project_id
cp dev.gcs.tfbackend.example dev.gcs.tfbackend   # fill in the state bucket
terraform init -backend-config=dev.gcs.tfbackend
terraform fmt -check && terraform validate
terraform plan -var-file=dev.tfvars
```

Every `apply` is announced with what it changes and run only after approval.
