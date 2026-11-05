<#
.SYNOPSIS
  Deploy one environment to GCP (Stage 7a). Windows PowerShell 5.1 or PowerShell 7 (also on Linux CI).

.DESCRIPTION
  Run from anywhere; paths resolve from the repo root. Steps, in order for a first deployment:
    state    create the Terraform state bucket (once per project)
    base     APIs + Artifact Registry + config store bucket (targeted apply; images need the
             registry, `config` needs the bucket)
    config   compile + verify a config bundle (config, skills, tenant groups.yaml/users.yaml),
             upload it to gs://<config_store_bucket>/bundles/<env>/ and point `current` at it.
             Cloud Run reads the active bundle and picks up a new one within ~2 minutes.
             -ConfigVersion <version>: only move `current` to an uploaded bundle (rollback).
    images   build + push mcp/agent/ingest/ui images (tag = git short SHA), mirror oauth2-proxy
    plan     full terraform plan -> infra/gcp/<env>.tfplan (review it)
    apply    apply the saved plan (deleted afterwards: it contains secret values)
    db       run the sdlc-db-setup job (bootstrap roles/schema + migrate)
    ingest   run the sdlc-ingest job
    urls     print app / MCP URLs and the OAuth callback to register on sdlc-client

  Tenant values (ENTRA_*) come from .env; group IDs from config/env/<env>/groups.yaml (git-ignored).
  First deployment with a config store bucket: state, base, config, images, plan, apply, db, ingest.
  A config-only change afterwards: commit, then `config` (no new images, no apply).
  `base` and `apply` change cloud resources and ask for confirmation unless -AutoApprove.
  Images and the plan use the same tag (the current commit), so commit before `images` and `plan`.

.EXAMPLE
  .\scripts\gcp_deploy.ps1 -EnvName dev -Step plan
#>
param(
    [Parameter(Mandatory = $true)][string]$EnvName,
    [Parameter(Mandatory = $true)]
    [ValidateSet('state', 'base', 'config', 'images', 'plan', 'apply', 'db', 'ingest', 'urls')]
    [string]$Step,
    [string]$ImageTag = '',      # override the git-SHA tag (e.g. to re-plan with already pushed images)
    [string]$ConfigVersion = '', # config step: activate this already uploaded bundle (rollback)
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

# Optional string in a tfvars file ('' when absent).
function Get-HclOptional([string]$File, [string]$Name) {
    $line = Select-String -Path $File -Pattern "^\s*$Name\s*=\s*`"(.*)`"" | Select-Object -First 1
    if (-not $line) { return '' }
    return $line.Matches[0].Groups[1].Value
}

$Project = Get-HclString $TfVars 'project_id'
$Region = Get-HclString $TfVars 'region'
$Registry = "$Region-docker.pkg.dev/$Project/sdlc"
$ConfigBucket = Get-HclOptional $TfVars 'config_store_bucket'   # '' = config baked into images
$BundleRoot = if ($ConfigBucket) { "gs://$ConfigBucket/bundles/$EnvName" } else { '' }

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
    # Optional direct members (version-02 N10): stored as a secret and mounted into the MCP service.
    $usersYaml = Join-Path $Root "config/env/$EnvName/users.yaml"
    $env:TF_VAR_users_yaml_path = if (Test-Path $usersYaml) { "../../config/env/$EnvName/users.yaml" } else { '' }
    if ($env:TF_VAR_users_yaml_path) { Write-Host "users.yaml: config/env/$EnvName/users.yaml" }
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
        Confirm-Change 'enable APIs, create the Artifact Registry repository and the config store bucket'
        $targets = @('-target=google_project_service.apis', '-target=google_artifact_registry_repository.sdlc')
        if ($ConfigBucket) { $targets += '-target=google_storage_bucket.config_store' }
        Invoke-Terraform (@('apply', '-input=false', '-auto-approve', "-var-file=$EnvName.tfvars") + $targets)
    }
    'images' {
        $tag = Get-ImageTag
        Invoke-Native 'gcloud' @('auth', 'configure-docker', "$Region-docker.pkg.dev", '--quiet')
        $images = [ordered]@{
            'core-mcp'      = 'mcp_servers/core_mcp/Dockerfile'
            'user-agent'    = 'agents/user_agent/Dockerfile'
            'ingest'        = 'ingest/bootstrap/Dockerfile'
            'ui-copilotkit' = 'ui/copilotkit/Dockerfile'   # CopilotKit chat app (version-01 M5)
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
    'config' {
        if (-not $BundleRoot) { throw "config_store_bucket is not set in $TfVars" }
        if ($ConfigVersion) {
            $version = $ConfigVersion
            if (-not (Test-Native 'gcloud' @('storage', 'objects', 'describe', "$BundleRoot/$version/manifest.json"))) {
                throw "bundle $version is not in $BundleRoot (list: gcloud storage ls $BundleRoot/)"
            }
        }
        else {
            [void](Get-ImageTag)   # refuses uncommitted changes: the bundle version starts with the commit
            if (-not (Test-Path (Join-Path $Root "config/env/$EnvName/groups.yaml"))) {
                throw "missing config/env/$EnvName/groups.yaml"
            }
            $local = Join-Path $Root ".bundles/$EnvName"   # git-ignored: bundles hold tenant files
            # uv reads --env-file shell-style (backslashes are escapes): pass forward slashes.
            $envFile = (Join-Path $Root '.env') -replace '\\', '/'
            $out = & uv run --env-file $envFile sdlc-config compile --env $EnvName `
                --config-dir (Join-Path $Root 'config') --out $local
            if ($LASTEXITCODE -ne 0) { throw 'sdlc-config compile failed (see above)' }
            $out | ForEach-Object { Write-Host $_ }
            $match = $out | Select-String -Pattern '^(compiled|unchanged) (\S+) ->' | Select-Object -First 1
            if (-not $match) { throw 'could not read the bundle version from sdlc-config compile' }
            $version = $match.Matches[0].Groups[2].Value
            # Bundles are immutable: upload the files first, move the pointer last.
            Invoke-Native 'gcloud' @('storage', 'rsync', '--recursive', (Join-Path $local $version), "$BundleRoot/$version")
        }
        Confirm-Change "activate config bundle $version for $EnvName"
        $pointer = Join-Path ([System.IO.Path]::GetTempPath()) "sdlc-current-$EnvName"
        [System.IO.File]::WriteAllText($pointer, $version)
        try { Invoke-Native 'gcloud' @('storage', 'cp', $pointer, "$BundleRoot/current") }
        finally { Remove-Item $pointer -ErrorAction SilentlyContinue }
        Write-Host "active: $version ($BundleRoot/current); Cloud Run picks it up within ~2 minutes"
    }
    'plan' {
        Set-TerraformEnv
        if (-not (Test-Path (Join-Path $Root "config/env/$EnvName/groups.yaml"))) {
            throw "missing config/env/$EnvName/groups.yaml"
        }
        # With a config store bucket, Cloud Run reads its config from there: an active bundle must
        # exist first, or the new MCP revision fails closed at startup.
        if ($BundleRoot -and -not (Test-Native 'gcloud' @('storage', 'objects', 'describe', "$BundleRoot/current"))) {
            throw "no active config bundle in ${BundleRoot}: run -Step base, then -Step config, first"
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
