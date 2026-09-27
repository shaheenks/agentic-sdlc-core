#!/usr/bin/env bash
# Deploy one environment to GCP (Stage 7a). Run from the repo root (Git Bash on Windows works).
#
#   scripts/gcp_deploy.sh <env> <step>
#
# Steps, in order for a first deployment:
#   state    create the Terraform state bucket (once per project)
#   base     APIs + Artifact Registry (targeted apply; images need the registry)
#   images   build + push mcp/agent/ingest images (tag = git short SHA), mirror oauth2-proxy
#   plan     full terraform plan -> infra/gcp/<env>.tfplan (review it)
#   apply    apply the saved plan
#   db       run the sdlc-db-setup job (bootstrap roles/schema + migrate)
#   ingest   run the sdlc-ingest job
#   urls     print app / MCP URLs and the OAuth callback to register on sdlc-client
#
# Tenant values (ENTRA_*) come from .env; group IDs from config/env/<env>/groups.yaml (git-ignored).
# `base` and `apply` change cloud resources: they ask for confirmation unless AUTO_APPROVE=1.
set -euo pipefail

ENV_NAME="${1:?usage: scripts/gcp_deploy.sh <env> <step>}"
STEP="${2:?usage: scripts/gcp_deploy.sh <env> <step>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$ROOT/infra/gcp"
TFVARS="$TF_DIR/$ENV_NAME.tfvars"
BACKEND="$TF_DIR/$ENV_NAME.gcs.tfbackend"
PLAN="$ENV_NAME.tfplan"

[ -f "$TFVARS" ] || { echo "missing $TFVARS" >&2; exit 1; }
tfvar() { sed -n "s/^$1 *= *\"\(.*\)\".*/\1/p" "$TFVARS"; }
PROJECT="$(tfvar project_id)"
REGION="$(tfvar region)"
REGISTRY="$REGION-docker.pkg.dev/$PROJECT/sdlc"
OAUTH2_PROXY_TAG="v7.15.4-alpine"

TERRAFORM="$(command -v terraform || true)"
if [ -z "$TERRAFORM" ]; then  # winget install without a restarted shell
  TERRAFORM="$(ls "$LOCALAPPDATA"/Microsoft/WinGet/Packages/Hashicorp.Terraform_*/terraform.exe 2>/dev/null | head -1)"
fi

env_value() { sed -n "s/^$1=//p" "$ROOT/.env" | tail -1 | tr -d '"\r'; }

image_tag() {
  if [ -n "${IMAGE_TAG:-}" ]; then echo "$IMAGE_TAG"; return; fi
  if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
    echo "uncommitted changes: commit first, or set IMAGE_TAG explicitly" >&2
    exit 1
  fi
  git -C "$ROOT" rev-parse --short=12 HEAD
}

terraform_env() {
  export TF_VAR_image_tag TF_VAR_entra_tenant_id TF_VAR_entra_api_client_id TF_VAR_entra_client_id \
    TF_VAR_entra_client_secret TF_VAR_entra_graph_client_secret TF_VAR_oauth2_proxy_tag
  TF_VAR_image_tag="$(image_tag)"
  TF_VAR_entra_tenant_id="$(env_value ENTRA_TENANT_ID)"
  TF_VAR_entra_api_client_id="$(env_value ENTRA_API_CLIENT_ID)"
  TF_VAR_entra_client_id="$(env_value ENTRA_CLIENT_ID)"
  TF_VAR_entra_client_secret="$(env_value ENTRA_CLIENT_SECRET)"
  TF_VAR_entra_graph_client_secret="$(env_value ENTRA_GRAPH_CLIENT_SECRET)"
  TF_VAR_oauth2_proxy_tag="$OAUTH2_PROXY_TAG"
  for v in TF_VAR_entra_tenant_id TF_VAR_entra_api_client_id TF_VAR_entra_client_id TF_VAR_entra_client_secret; do
    [ -n "${!v}" ] || { echo "$v is empty (check .env)" >&2; exit 1; }
  done
}

tf() { (cd "$TF_DIR" && "$TERRAFORM" "$@"); }
tf_init() { tf init -input=false -reconfigure -backend-config="$ENV_NAME.gcs.tfbackend" >/dev/null; }
approve_flag() { [ "${AUTO_APPROVE:-0}" = "1" ] && echo "-auto-approve" || true; }

case "$STEP" in
  state)
    bucket="$(sed -n 's/^bucket *= *"\(.*\)"/\1/p' "$BACKEND")"
    if gcloud storage buckets describe "gs://$bucket" --project "$PROJECT" >/dev/null 2>&1; then
      echo "state bucket gs://$bucket exists"
    else
      gcloud storage buckets create "gs://$bucket" --project "$PROJECT" --location "$REGION" \
        --uniform-bucket-level-access --public-access-prevention
      gcloud storage buckets update "gs://$bucket" --versioning
    fi
    ;;
  base)
    terraform_env
    tf_init
    tf apply -input=false $(approve_flag) -var-file="$ENV_NAME.tfvars" \
      -target=google_project_service.apis -target=google_artifact_registry_repository.sdlc
    ;;
  images)
    tag="$(image_tag)"
    gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet >/dev/null
    for spec in "mcp-bootstrap:mcp_servers/bootstrap/Dockerfile" \
                "agent-bootstrap:agents/bootstrap/Dockerfile" \
                "ingest:ingest/bootstrap/Dockerfile"; do
      name="${spec%%:*}"; dockerfile="${spec#*:}"
      docker build --platform linux/amd64 -f "$ROOT/$dockerfile" -t "$REGISTRY/$name:$tag" "$ROOT"
      docker push "$REGISTRY/$name:$tag"
    done
    # Cloud Run pulls only from Artifact Registry / Docker Hub: mirror oauth2-proxy from quay.io.
    docker pull --platform linux/amd64 "quay.io/oauth2-proxy/oauth2-proxy:$OAUTH2_PROXY_TAG"
    docker tag "quay.io/oauth2-proxy/oauth2-proxy:$OAUTH2_PROXY_TAG" "$REGISTRY/oauth2-proxy:$OAUTH2_PROXY_TAG"
    docker push "$REGISTRY/oauth2-proxy:$OAUTH2_PROXY_TAG"
    echo "pushed images with tag $tag"
    ;;
  plan)
    terraform_env
    [ -f "$ROOT/config/env/$ENV_NAME/groups.yaml" ] || { echo "missing config/env/$ENV_NAME/groups.yaml" >&2; exit 1; }
    tf_init
    tf plan -input=false -var-file="$ENV_NAME.tfvars" -out="$PLAN"
    ;;
  apply)
    [ -f "$TF_DIR/$PLAN" ] || { echo "run the plan step first" >&2; exit 1; }
    if [ "${AUTO_APPROVE:-0}" != "1" ]; then
      read -r -p "apply $TF_DIR/$PLAN to project $PROJECT? [y/N] " answer
      [ "$answer" = "y" ] || { echo "aborted"; exit 1; }
    fi
    tf_init
    tf apply -input=false "$PLAN"
    rm -f "$TF_DIR/$PLAN"
    ;;
  db | ingest)
    job="sdlc-$([ "$STEP" = db ] && echo db-setup || echo ingest)-$ENV_NAME"
    gcloud run jobs execute "$job" --project "$PROJECT" --region "$REGION" --wait
    ;;
  urls)
    tf_init
    tf output
    ;;
  *)
    echo "unknown step: $STEP" >&2
    exit 1
    ;;
esac
