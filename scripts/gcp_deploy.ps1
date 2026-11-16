<#
.SYNOPSIS
  Deploy one environment to GCP (Stage 7a). Windows PowerShell 5.1 or PowerShell 7 (also on Linux CI).

.DESCRIPTION
  Run from anywhere; paths resolve from the repo root. Steps, in order for a first deployment:
    state    create the Terraform state bucket (once per project)
    base     APIs + Artifact Registry + config store bucket (targeted apply; images need the
             registry, `config` needs the bucket)
    config   compile + verify a config bundle (config, skills, the tenant's users.yaml),
             upload it to gs://<config_store_bucket>/bundles/<env>/ and point `current` at it.
             Cloud Run reads the active bundle and picks up a new one within ~2 minutes.
             -ConfigVersion <version>: only move `current` to an uploaded bundle (rollback).
    images   build + push the images whose tag is not in the registry yet, mirror oauth2-proxy.
             Each image's tag is a hash of its own committed build inputs (scripts/build_tag.py,
             CH-0024), so an unchanged image is skipped. -Rebuild builds them all.
    plan     full terraform plan -> infra/gcp/<env>.tfplan (review it)
    apply    apply the saved plan (deleted afterwards: it contains secret values)
    db       run the sdlc-db-setup job (bootstrap roles/schema + migrate)
    ingest   run the sdlc-ingest job
    urls     print app / MCP URLs and the OAuth callback to register on sdlc-client

  Tenant values (ENTRA_*) come from .env. Membership comes from Entra app roles (CH-0011); there is
  no group map (CH-0012). The GCP stack's OAuth client IDs (SDLC_OAUTH_CLIENT_IDS, CH-0022) also
  come from .env; its groups and domains are config.
  First deployment with a config store bucket: state, base, config, images, plan, apply, db, ingest.
  A config-only change afterwards: commit, then `config` (no new images, no apply).
  `base` and `apply` change cloud resources and ask for confirmation unless -AutoApprove.
  Images and the plan compute the same tags from the committed files, so commit before `images` and
  `plan`; `plan` stops if a tag is not pushed yet. Only services whose image tag changed roll out.

.EXAMPLE
  .\scripts\gcp_deploy.ps1 -EnvName dev -Step plan
#>
param(
    [Parameter(Mandatory = $true)][string]$EnvName,
    [Parameter(Mandatory = $true)]
    [ValidateSet('state', 'base', 'config', 'images', 'plan', 'apply', 'db', 'ingest', 'urls')]
    [string]$Step,
    [string]$ImageTag = '',      # one tag for every image (re-plan or roll back to tags pushed before CH-0024)
    [string]$ConfigVersion = '', # config step: activate this already uploaded bundle (rollback)
    [switch]$AutoApprove,
    [switch]$Rebuild             # images step: build and push every image, pushed or not
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
    # Reads .env like `uv run --env-file` does: a quoted value is taken as is; an unquoted value
    # ends at a ` #` comment (CH-0022 fix: a trailing comment had reached Cloud Run as a value).
    $line = Get-Content (Join-Path $Root '.env') | Where-Object { $_ -match "^$Name=" } | Select-Object -Last 1
    if (-not $line) { return '' }
    $value = ($line -replace "^$Name=", '').Trim()
    if ($value -match '^"([^"]*)"') { return $Matches[1] }
    if ($value -match "^'([^']*)'") { return $Matches[1] }
    return ($value -replace '\s+#.*$', '').Trim()
}

function Assert-Committed([string]$Why) {
    $dirty = git -C $Root status --porcelain
    if ($dirty) { throw "uncommitted changes: commit first ($Why)" }
}

# Terraform key -> name, dockerfile, tag. The image list and the tags come from scripts/build_tag.py
# (CH-0024): each tag is a hash of the image's own committed build inputs. -ImageTag overrides all.
function Get-BuildTags {
    if (-not $ImageTag) { Assert-Committed 'image tags come from committed files; or pass -ImageTag' }
    $json = & uv run python (Join-Path $Root 'scripts/build_tag.py') --root $Root
    if ($LASTEXITCODE -ne 0) { throw 'scripts/build_tag.py failed (see above)' }
    $images = [ordered]@{}
    foreach ($p in (($json -join "`n") | ConvertFrom-Json).PSObject.Properties) {
        $tag = if ($ImageTag) { $ImageTag } else { $p.Value.tag }
        $images[$p.Name] = [pscustomobject]@{ name = $p.Value.name; dockerfile = $p.Value.dockerfile; tag = $tag }
    }
    return $images
}

function Test-ImagePushed([string]$Ref) {
    return (Test-Native 'gcloud' @('artifacts', 'docker', 'images', 'describe', $Ref, '--quiet'))
}

function Set-TerraformEnv {
    $script:BuildImages = Get-BuildTags
    $tags = [ordered]@{}
    foreach ($key in $script:BuildImages.Keys) { $tags[$key] = $script:BuildImages[$key].tag }
    $env:TF_VAR_image_tags = ($tags | ConvertTo-Json -Compress)
    $env:TF_VAR_oauth2_proxy_tag = $OAuth2ProxyTag
    $env:TF_VAR_entra_tenant_id = Get-DotEnv 'ENTRA_TENANT_ID'
    $env:TF_VAR_entra_api_client_id = Get-DotEnv 'ENTRA_API_CLIENT_ID'
    $env:TF_VAR_entra_client_id = Get-DotEnv 'ENTRA_CLIENT_ID'
    $env:TF_VAR_entra_client_secret = Get-DotEnv 'ENTRA_CLIENT_SECRET'
    # GCP stack (CH-0022): the audience core_mcp_gcp accepts; empty = it refuses to start.
    $env:TF_VAR_google_oauth_client_ids = Get-DotEnv 'SDLC_OAUTH_CLIENT_IDS'
    # The native chat UI's server-side sign-in (CH-0016): the Web OAuth client.
    $env:TF_VAR_google_web_client_id = Get-DotEnv 'SDLC_GOOGLE_WEB_CLIENT_ID'
    $env:TF_VAR_google_web_client_secret = Get-DotEnv 'SDLC_GOOGLE_WEB_CLIENT_SECRET'
    # IAP's own OAuth client for the native chat UI (sdlc-iap-web, CH-0016).
    $env:TF_VAR_google_iap_client_id = Get-DotEnv 'SDLC_GOOGLE_IAP_CLIENT_ID'
    $env:TF_VAR_google_iap_client_secret = Get-DotEnv 'SDLC_GOOGLE_IAP_CLIENT_SECRET'
    # Optional direct members (version-02 N10): stored as a secret and mounted into the MCP service.
    $usersYaml = Join-Path $Root "config/env/$EnvName/users.yaml"
    $env:TF_VAR_users_yaml_path = if (Test-Path $usersYaml) { "../../config/env/$EnvName/users.yaml" } else { '' }
    if ($env:TF_VAR_users_yaml_path) { Write-Host "users.yaml: config/env/$EnvName/users.yaml" }
    foreach ($v in 'entra_tenant_id', 'entra_api_client_id', 'entra_client_id', 'entra_client_secret') {
        if (-not (Get-Item "env:TF_VAR_$v").Value) { throw "TF_VAR_$v is empty (check .env)" }
    }
    Write-Host "image tags: $(($tags.Keys | ForEach-Object { "$_=$($tags[$_])" }) -join ', ')"
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
        $images = Get-BuildTags
        Invoke-Native 'gcloud' @('auth', 'configure-docker', "$Region-docker.pkg.dev", '--quiet')
        $summary = @()
        foreach ($key in $images.Keys) {
            $image = $images[$key]
            $ref = "$Registry/$($image.name):$($image.tag)"
            if (-not $Rebuild -and (Test-ImagePushed $ref)) {
                $summary += "  $($image.name):$($image.tag) unchanged (already pushed)"
                continue
            }
            Invoke-Native 'docker' @('build', '--platform', 'linux/amd64', '-f', (Join-Path $Root $image.dockerfile),
                '-t', $ref, $Root)
            Invoke-Native 'docker' @('push', $ref)
            $summary += "  $($image.name):$($image.tag) built and pushed"
        }
        # Cloud Run pulls only from Artifact Registry / Docker Hub: mirror oauth2-proxy from quay.io.
        $mirror = "$Registry/oauth2-proxy:$OAuth2ProxyTag"
        if (-not $Rebuild -and (Test-ImagePushed $mirror)) {
            $summary += "  oauth2-proxy:$OAuth2ProxyTag unchanged (already mirrored)"
        }
        else {
            $upstream = "quay.io/oauth2-proxy/oauth2-proxy:$OAuth2ProxyTag"
            Invoke-Native 'docker' @('pull', '--platform', 'linux/amd64', $upstream)
            Invoke-Native 'docker' @('tag', $upstream, $mirror)
            Invoke-Native 'docker' @('push', $mirror)
            $summary += "  oauth2-proxy:$OAuth2ProxyTag mirrored"
        }
        Write-Host 'images:'
        $summary | ForEach-Object { Write-Host $_ }
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
            Assert-Committed 'the bundle version starts with the commit'
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
        # With a config store bucket, Cloud Run reads its config from there: an active bundle must
        # exist first, or the new MCP revision fails closed at startup.
        if ($BundleRoot -and -not (Test-Native 'gcloud' @('storage', 'objects', 'describe', "$BundleRoot/current"))) {
            throw "no active config bundle in ${BundleRoot}: run -Step base, then -Step config, first"
        }
        # Every image the plan names must be pushed, or the new revisions cannot start.
        $missing = @($script:BuildImages.Values | Where-Object { -not (Test-ImagePushed "$Registry/$($_.name):$($_.tag)") } |
            ForEach-Object { "$($_.name):$($_.tag)" })
        if ($missing) { throw "not in the registry: $($missing -join ', '); run -Step images first" }
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
