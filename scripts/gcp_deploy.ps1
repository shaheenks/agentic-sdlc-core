<#
.SYNOPSIS
  Deploy one environment to GCP (Stage 7a). Windows PowerShell 5.1 or PowerShell 7 (also on Linux CI).

.DESCRIPTION
  Run from anywhere; paths resolve from the repo root. Steps, in order for a first deployment:
    state    create the Terraform state bucket (once per project)
    base     APIs + Artifact Registry (targeted apply; images need the registry)
    images   build + push mcp/agent/ingest images (tag = git short SHA), mirror oauth2-proxy
    plan     full terraform plan -> infra/gcp/<env>.tfplan (review it)
    apply    apply the saved plan (deleted afterwards: it contains secret values)
    db       run the sdlc-db-setup job (bootstrap roles/schema + migrate)
    ingest   run the sdlc-ingest job
    urls     print app / MCP URLs and the OAuth callback to register on sdlc-client

  Tenant values (ENTRA_*) come from .env; group IDs from config/env/<env>/groups.yaml (git-ignored).
  `base` and `apply` change cloud resources and ask for confirmation unless -AutoApprove.
  Images and the plan use the same tag (the current commit), so commit before `images` and `plan`.

.EXAMPLE
  .\scripts\gcp_deploy.ps1 -EnvName staging -Step plan
#>
param(
    [Parameter(Mandatory = $true)][string]$EnvName,
    [Parameter(Mandatory = $true)]
    [ValidateSet('state', 'base', 'images', 'plan', 'apply', 'db', 'ingest', 'urls')]
    [string]$Step,
    [string]$ImageTag = '',      # override the git-SHA tag (e.g. to re-plan with already pushed images)
    [switch]$AutoApprove
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$TfDir = Join-Path $Root 'infra/gcp'
$TfVars = Join-Path $TfDir "$EnvName.tfvars"
$Backend = Join-Path $TfDir "$EnvName.gcs.tfbackend"
$Plan = "$EnvName.tfplan"
$OAuth2ProxyTag = 'v7.15.4-alpine'

if (-not (Test-Path $TfVars)) { throw "missing $TfVars" }

function Get-HclString([string]$File, [string]$Name) {
    $line = Select-String -Path $File -Pattern "^\s*$Name\s*=\s*`"(.*)`"" | Select-Object -First 1
    if (-not $line) { throw "$Name not set in $File" }
    return $line.Matches[0].Groups[1].Value
}

$Project = Get-HclString $TfVars 'project_id'
$Region = Get-HclString $TfVars 'region'
$Registry = "$Region-docker.pkg.dev/$Project/sdlc"

$Terraform = (Get-Command terraform -ErrorAction SilentlyContinue).Source
if (-not $Terraform) {   # winget install without a restarted shell
    $Terraform = Get-ChildItem "$env:LOCALAPPDATA/Microsoft/WinGet/Packages/Hashicorp.Terraform_*/terraform.exe" `
        -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}

# Run a native command; fail on a non-zero exit code. stderr is not redirected (PowerShell 5.1
# turns redirected native stderr into errors).
function Invoke-Native([string]$Exe, [string[]]$ArgList) {
    & $Exe @ArgList
    if ($LASTEXITCODE -ne 0) { throw "$Exe $($ArgList -join ' ') failed with exit code $LASTEXITCODE" }
}

# True if a native command succeeds; all output discarded.
function Test-Native([string]$Exe, [string[]]$ArgList) {
    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Exe @ArgList *> $null; return ($LASTEXITCODE -eq 0) }
    finally { $ErrorActionPreference = $saved }
}

function Get-DotEnv([string]$Name) {
    $line = Get-Content (Join-Path $Root '.env') | Where-Object { $_ -match "^$Name=" } | Select-Object -Last 1
    if (-not $line) { return '' }
    return ($line -replace "^$Name=", '').Trim().Trim('"')
}

function Get-ImageTag {
    if ($ImageTag) { return $ImageTag }
    $dirty = git -C $Root status --porcelain
    if ($dirty) { throw 'uncommitted changes: commit first, or pass -ImageTag explicitly' }
    return (git -C $Root rev-parse --short=12 HEAD).Trim()
}

function Set-TerraformEnv {
    $env:TF_VAR_image_tag = Get-ImageTag
    $env:TF_VAR_oauth2_proxy_tag = $OAuth2ProxyTag
    $env:TF_VAR_entra_tenant_id = Get-DotEnv 'ENTRA_TENANT_ID'
    $env:TF_VAR_entra_api_client_id = Get-DotEnv 'ENTRA_API_CLIENT_ID'
    $env:TF_VAR_entra_client_id = Get-DotEnv 'ENTRA_CLIENT_ID'
    $env:TF_VAR_entra_client_secret = Get-DotEnv 'ENTRA_CLIENT_SECRET'
    $env:TF_VAR_entra_graph_client_secret = Get-DotEnv 'ENTRA_GRAPH_CLIENT_SECRET'
    foreach ($v in 'entra_tenant_id', 'entra_api_client_id', 'entra_client_id', 'entra_client_secret') {
        if (-not (Get-Item "env:TF_VAR_$v").Value) { throw "TF_VAR_$v is empty (check .env)" }
    }
    Write-Host "image tag: $env:TF_VAR_image_tag"
}

function Invoke-Terraform([string[]]$ArgList) {
    if (-not $Terraform) { throw 'terraform not found (winget install Hashicorp.Terraform)' }
    Push-Location $TfDir
    try { Invoke-Native $Terraform $ArgList }
    finally { Pop-Location }
}

function Initialize-Terraform {
    Invoke-Terraform @('init', '-input=false', '-reconfigure', "-backend-config=$EnvName.gcs.tfbackend") | Out-Null
}

function Confirm-Change([string]$What) {
    if ($AutoApprove) { return }
    $answer = Read-Host "$What in project $Project? [y/N]"
    if ($answer -ne 'y') { throw 'aborted' }
}

switch ($Step) {
    'state' {
        $bucket = Get-HclString $Backend 'bucket'
        if (Test-Native 'gcloud' @('storage', 'buckets', 'describe', "gs://$bucket", '--project', $Project)) {
            Write-Host "state bucket gs://$bucket exists"
        }
        else {
            Invoke-Native 'gcloud' @('storage', 'buckets', 'create', "gs://$bucket", '--project', $Project,
                '--location', $Region, '--uniform-bucket-level-access', '--public-access-prevention')
            Invoke-Native 'gcloud' @('storage', 'buckets', 'update', "gs://$bucket", '--versioning')
        }
    }
    'base' {
        Set-TerraformEnv
        Initialize-Terraform
        Confirm-Change 'enable APIs and create the Artifact Registry repository'
        Invoke-Terraform @('apply', '-input=false', '-auto-approve', "-var-file=$EnvName.tfvars",
            '-target=google_project_service.apis', '-target=google_artifact_registry_repository.sdlc')
    }
    'images' {
        $tag = Get-ImageTag
        Invoke-Native 'gcloud' @('auth', 'configure-docker', "$Region-docker.pkg.dev", '--quiet')
        $images = [ordered]@{
            'mcp-bootstrap'   = 'mcp_servers/bootstrap/Dockerfile'
            'agent-bootstrap' = 'agents/bootstrap/Dockerfile'
            'ingest'          = 'ingest/bootstrap/Dockerfile'
        }
        foreach ($name in $images.Keys) {
            Invoke-Native 'docker' @('build', '--platform', 'linux/amd64', '-f', (Join-Path $Root $images[$name]),
                '-t', "$Registry/${name}:$tag", $Root)
            Invoke-Native 'docker' @('push', "$Registry/${name}:$tag")
        }
        # Cloud Run pulls only from Artifact Registry / Docker Hub: mirror oauth2-proxy from quay.io.
        $upstream = "quay.io/oauth2-proxy/oauth2-proxy:$OAuth2ProxyTag"
        Invoke-Native 'docker' @('pull', '--platform', 'linux/amd64', $upstream)
        Invoke-Native 'docker' @('tag', $upstream, "$Registry/oauth2-proxy:$OAuth2ProxyTag")
        Invoke-Native 'docker' @('push', "$Registry/oauth2-proxy:$OAuth2ProxyTag")
        Write-Host "pushed images with tag $tag"
    }
    'plan' {
        Set-TerraformEnv
        if (-not (Test-Path (Join-Path $Root "config/env/$EnvName/groups.yaml"))) {
            throw "missing config/env/$EnvName/groups.yaml"
        }
        Initialize-Terraform
        Invoke-Terraform @('plan', '-input=false', "-var-file=$EnvName.tfvars", "-out=$Plan")
    }
    'apply' {
        if (-not (Test-Path (Join-Path $TfDir $Plan))) { throw 'run the plan step first' }
        Confirm-Change "apply infra/gcp/$Plan"
        Initialize-Terraform
        try { Invoke-Terraform @('apply', '-input=false', $Plan) }
        finally { Remove-Item (Join-Path $TfDir $Plan) -ErrorAction SilentlyContinue }
    }
    { $_ -in 'db', 'ingest' } {
        $job = if ($Step -eq 'db') { "sdlc-db-setup-$EnvName" } else { "sdlc-ingest-$EnvName" }
        Invoke-Native 'gcloud' @('run', 'jobs', 'execute', $job, '--project', $Project, '--region', $Region, '--wait')
    }
    'urls' {
        Initialize-Terraform
        Invoke-Terraform @('output')
    }
}
