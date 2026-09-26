<#
.SYNOPSIS
  Idempotent Entra ID setup for the agentic SDLC platform (Stage 2).
  Works in Windows PowerShell 5.1 and PowerShell 7. Safe to re-run: finds and completes
  existing objects instead of duplicating them.

.DESCRIPTION
  Creates or updates:
    - app sdlc-mcp (API): identifier URI, access_as_user scope, v2 tokens, groups claim,
      Azure CLI pre-authorized (dev testing), assignment required
    - security groups sdlc-eng-all, sdlc-payments-devs, sdlc-payments-leads,
      sdlc-platform-devs, sdlc-platform-admins
    - memberships: user A = eng-all + payments-devs, user B = eng-all + platform-devs
    - app assignments: groups (P1/P2) or the two test users (Free tier)
    - app sdlc-client (web, for oauth2-proxy in Stage 2d): redirect URI, access_as_user
      permission + admin consent, optional client secret

  Why a script: on Windows `az` is az.cmd, so every argument goes through cmd.exe. JSON
  bodies and OData filters with parentheses get mangled. This script passes JSON via
  temp files (--body @file) and avoids special characters in arguments.

.EXAMPLE
  az login --tenant <tenant> --allow-no-subscriptions
  .\scripts\entra_setup.ps1 -TestUserA ad.paul@contoso.onmicrosoft.com -TestUserB ad.b@contoso.onmicrosoft.com -DryRun
  .\scripts\entra_setup.ps1 -TestUserA ... -TestUserB ... -NewClientSecret -WriteLocalFiles
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TestUserA,   # eng-all + payments-devs
    [Parameter(Mandatory = $true)][string]$TestUserB,   # eng-all + platform-devs
    [string]$IdentifierUri = '',   # default api://<sdlc-mcp appId> (matches config/platform.yaml)
    # oauth2-proxy callbacks: local + public (Cloudflare Tunnel). Existing URIs are kept.
    [string[]]$RedirectUri = @('http://localhost:4180/oauth2/callback', 'https://app-sdlc-dev.shaheenks.co.in/oauth2/callback'),
    [switch]$NewClientSecret,   # create a new sdlc-client secret (printed once / written to .env)
    [switch]$WriteLocalFiles,   # update .env and config/env/local/groups.yaml with the real IDs
    [switch]$DryRun,            # read-only: print planned changes, modify nothing
    [switch]$NoAzCliPreAuth     # prod/enterprise: no Azure CLI pre-authorization (removes it if present)
)

$ErrorActionPreference = 'Stop'
$GraphBase = 'https://graph.microsoft.com/v1.0'
$AzCliClientId = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'   # Azure CLI (pre-authorized for dev tokens)
$DefaultAccessRole = '00000000-0000-0000-0000-000000000000'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$GroupNames = [ordered]@{
    'eng-all'         = 'sdlc-eng-all'
    'payments-devs'   = 'sdlc-payments-devs'
    'payments-leads'  = 'sdlc-payments-leads'
    'platform-devs'   = 'sdlc-platform-devs'
    'platform-admins' = 'sdlc-platform-admins'
}
$Memberships = @(
    @{ User = $TestUserA; Groups = @('eng-all', 'payments-devs') },
    @{ User = $TestUserB; Groups = @('eng-all', 'platform-devs') }
)

# ---------------------------------------------------------------- helpers
function Invoke-Az {
    # Run az; return stdout text; throw with stderr on failure. stderr goes to a file because
    # Windows PowerShell 5.1 turns redirected native stderr into errors.
    $errFile = [IO.Path]::GetTempFileName()
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & az @args 2> $errFile
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    $err = Get-Content -Raw -Path $errFile -ErrorAction SilentlyContinue
    Remove-Item $errFile -ErrorAction SilentlyContinue
    if ($code -ne 0) { throw "az $($args -join ' ') failed (exit $code):`n$err" }
    return ($out -join "`n")
}

function Invoke-AzJson {
    $text = Invoke-Az @args '-o' 'json'
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }
    return ($text | ConvertFrom-Json)
}

function Invoke-Graph([string]$Method, [string]$Path, $Body = $null) {
    $azArgs = @('rest', '--method', $Method, '--url', "$GraphBase$Path")
    $bodyFile = $null
    if ($null -ne $Body) {
        $bodyFile = [IO.Path]::GetTempFileName()
        # UTF-8 without BOM (Set-Content in 5.1 would add a BOM)
        [IO.File]::WriteAllText($bodyFile, ($Body | ConvertTo-Json -Depth 20), (New-Object Text.UTF8Encoding $false))
        $azArgs += @('--headers', 'Content-Type=application/json', '--body', "@$bodyFile")
    }
    try { return Invoke-AzJson @azArgs }
    finally { if ($bodyFile) { Remove-Item $bodyFile -ErrorAction SilentlyContinue } }
}

function Invoke-Change([string]$Description, [scriptblock]$Action) {
    if ($DryRun) { Write-Host "  [dry-run] would: $Description" -ForegroundColor Yellow; return $null }
    Write-Host "  -> $Description" -ForegroundColor Cyan
    return (& $Action)
}

function Get-Single($Items, [string]$What) {
    $list = @($Items)
    if ($list.Count -gt 1) { throw "More than one $What found; clean up duplicates first." }
    if ($list.Count -eq 1) { return $list[0] }
    return $null
}

# ---------------------------------------------------------------- 0. context
$account = Invoke-AzJson account show
$TenantId = $account.tenantId
Write-Host "Tenant $TenantId as $($account.user.name)$(if ($DryRun) { '  (DRY RUN)' })" -ForegroundColor Green
$skus = @((Invoke-Graph GET '/subscribedSkus').value)
$plans = @($skus | ForEach-Object { $_.servicePlans } | ForEach-Object { $_.servicePlanName })
$IsPremium = [bool]($plans -match '^AAD_PREMIUM')
$GroupClaims = if ($IsPremium) { 'ApplicationGroup' } else { 'SecurityGroup' }
Write-Host "Entra tier: $(if ($IsPremium) { 'P1/P2' } else { 'Free' }) -> groupMembershipClaims=$GroupClaims, assign $(if ($IsPremium) { 'groups' } else { 'users' }) to sdlc-mcp"

# ---------------------------------------------------------------- 1. API app: sdlc-mcp
Write-Host "`n[1] App sdlc-mcp" -ForegroundColor Green
$api = Get-Single (Invoke-AzJson ad app list --display-name sdlc-mcp) 'app sdlc-mcp'
if (-not $api) {
    $api = Invoke-Change 'create app registration sdlc-mcp' {
        Invoke-AzJson ad app create --display-name sdlc-mcp --sign-in-audience AzureADMyOrg
    }
}
$apiAppId = if ($api) { $api.appId } else { '<new sdlc-mcp appId>' }
if (-not $IdentifierUri) { $IdentifierUri = "api://$apiAppId" }
$existingScope = if ($api) { @($api.api.oauth2PermissionScopes) | Where-Object { $_.value -eq 'access_as_user' } } else { $null }
$ScopeId = if ($existingScope) { $existingScope.id } else { [guid]::NewGuid().ToString() }
Write-Host "  appId=$apiAppId scopeId=$ScopeId"

$scopeDef = @{
    id = $ScopeId; value = 'access_as_user'; type = 'User'; isEnabled = $true
    adminConsentDisplayName = 'Use SDLC tools as the signed-in user'
    adminConsentDescription = 'Lets the app call the SDLC MCP server on behalf of the signed-in user.'
    userConsentDisplayName  = 'Use SDLC tools as you'
    userConsentDescription  = 'Lets the app call the SDLC MCP server on your behalf.'
}
$apiSettings = @{
    requestedAccessTokenVersion = 2
    oauth2PermissionScopes      = @($scopeDef)
}

# 1a. identifier URI (fall back to api://<appId> if a tenant policy rejects the custom one)
$currentUris = if ($api) { @($api.identifierUris) } else { @() }
$EffectiveUri = $IdentifierUri
if ($currentUris -contains $IdentifierUri) {
    Write-Host "  identifier URI ok: $IdentifierUri"
} elseif ($currentUris -contains "api://$apiAppId") {
    $EffectiveUri = "api://$apiAppId"
    Write-Host "  identifier URI ok: $EffectiveUri"
} else {
    Invoke-Change "set identifier URI $IdentifierUri" {
        try { Invoke-Graph PATCH "/applications/$($api.id)" @{ identifierUris = @($IdentifierUri) } | Out-Null }
        catch {
            Write-Warning "custom identifier URI rejected; falling back to api://$apiAppId"
            Invoke-Graph PATCH "/applications/$($api.id)" @{ identifierUris = @("api://$apiAppId") } | Out-Null
            $script:EffectiveUri = "api://$apiAppId"
        }
    } | Out-Null
}

# 1b. scope + v2 tokens + groups claim (scope must exist before it can be pre-authorized)
Invoke-Change 'set access_as_user scope, v2 access tokens, groups claim' {
    Invoke-Graph PATCH "/applications/$($api.id)" @{
        api                   = $apiSettings
        groupMembershipClaims = $GroupClaims
        optionalClaims        = @{ accessToken = @(@{ name = 'groups' }); idToken = @(); saml2Token = @() }
    } | Out-Null
} | Out-Null
# 1c. pre-authorize Azure CLI (dev: az account get-access-token for the whoami check).
#     -NoAzCliPreAuth removes it: required outside dev (see plan, Enterprise gap E6).
if ($NoAzCliPreAuth) {
    $apiSettings.preAuthorizedApplications = @()
    $preAuthDescription = 'remove Azure CLI pre-authorization'
} else {
    $apiSettings.preAuthorizedApplications = @(@{ appId = $AzCliClientId; delegatedPermissionIds = @($ScopeId) })
    $preAuthDescription = 'pre-authorize Azure CLI for access_as_user (dev testing)'
}
Invoke-Change $preAuthDescription {
    Invoke-Graph PATCH "/applications/$($api.id)" @{ api = $apiSettings } | Out-Null
} | Out-Null

# 1d. service principal with assignment required
$apiSp = if ($api) { Get-Single (Invoke-AzJson ad sp list --filter "appId eq '$apiAppId'") 'sdlc-mcp service principal' } else { $null }
if (-not $apiSp) {
    $apiSp = Invoke-Change 'create service principal for sdlc-mcp' { Invoke-AzJson ad sp create --id $apiAppId }
}
if ($apiSp -and $apiSp.appRoleAssignmentRequired) {
    Write-Host '  assignment required: ok'
} else {
    Invoke-Change 'require assignment (only assigned users/groups can get tokens)' {
        Invoke-Graph PATCH "/servicePrincipals/$($apiSp.id)" @{ appRoleAssignmentRequired = $true } | Out-Null
    } | Out-Null
}

# ---------------------------------------------------------------- 2. groups, members, assignments
Write-Host "`n[2] Groups and test users" -ForegroundColor Green
$GroupIds = [ordered]@{}
foreach ($alias in $GroupNames.Keys) {
    $name = $GroupNames[$alias]
    $g = Get-Single (Invoke-AzJson ad group list --display-name $name) "group $name"
    if (-not $g) {
        $g = Invoke-Change "create security group $name" {
            Invoke-AzJson ad group create --display-name $name --mail-nickname $name
        }
    }
    $GroupIds[$alias] = if ($g) { $g.id } else { "<new $name id>" }
    Write-Host ("  {0,-16} {1,-22} {2}" -f $alias, $name, $GroupIds[$alias])
}

$UserIds = @{}
foreach ($m in $Memberships) {
    $u = Invoke-AzJson ad user show --id $m.User
    $UserIds[$m.User] = $u.id
    foreach ($alias in $m.Groups) {
        $gid = $GroupIds[$alias]
        $isMember = if ($gid -like '<new*') { $false } else {
            (Invoke-AzJson ad group member check --group $gid --member-id $u.id).value
        }
        if ($isMember) { Write-Host "  $($m.User) in $($GroupNames[$alias]): ok" }
        else { Invoke-Change "add $($m.User) to $($GroupNames[$alias])" {
            Invoke-Az ad group member add --group $gid --member-id $u.id | Out-Null } | Out-Null }
    }
}

$assigned = if ($apiSp) { @((Invoke-Graph GET "/servicePrincipals/$($apiSp.id)/appRoleAssignedTo").value | ForEach-Object { $_.principalId }) } else { @() }
$toAssign = if ($IsPremium) { @($GroupIds.Values) } else { @($UserIds.Values) }
foreach ($principalId in $toAssign) {
    if ($assigned -contains $principalId) { Write-Host "  assignment $principalId : ok"; continue }
    Invoke-Change "assign $principalId to sdlc-mcp" {
        Invoke-Graph POST "/servicePrincipals/$($apiSp.id)/appRoleAssignedTo" @{
            principalId = $principalId; resourceId = $apiSp.id; appRoleId = $DefaultAccessRole
        } | Out-Null
    } | Out-Null
}

# ---------------------------------------------------------------- 3. client app: sdlc-client
Write-Host "`n[3] App sdlc-client" -ForegroundColor Green
$client = Get-Single (Invoke-AzJson ad app list --display-name sdlc-client) 'app sdlc-client'
if (-not $client) {
    $client = Invoke-Change 'create app registration sdlc-client' {
        Invoke-AzJson ad app create --display-name sdlc-client --sign-in-audience AzureADMyOrg --web-redirect-uris @RedirectUri
    }
}
$clientAppId = if ($client) { $client.appId } else { '<new sdlc-client appId>' }
Write-Host "  appId=$clientAppId"

$redirects = if ($client) { @($client.web.redirectUris) } else { @($RedirectUri) }
$missingRedirects = @($RedirectUri | Where-Object { $redirects -notcontains $_ })
if ($missingRedirects.Count -eq 0) { Write-Host "  redirect URIs ok: $($redirects -join ', ')" }
else {
    Invoke-Change "add redirect URI(s) $($missingRedirects -join ', ')" {
        Invoke-Graph PATCH "/applications/$($client.id)" @{ web = @{ redirectUris = @($redirects + $missingRedirects) } } | Out-Null
    } | Out-Null
}

$hasPerm = $client -and (@($client.requiredResourceAccess) | Where-Object {
        $_.resourceAppId -eq $apiAppId -and (@($_.resourceAccess) | Where-Object { $_.id -eq $ScopeId }) })
if ($hasPerm) { Write-Host '  permission sdlc-mcp/access_as_user ok' }
else {
    Invoke-Change 'add delegated permission sdlc-mcp/access_as_user' {
        Invoke-Az ad app permission add --id $clientAppId --api $apiAppId --api-permissions "$ScopeId=Scope" | Out-Null
    } | Out-Null
}

$clientSp = if ($client) { Get-Single (Invoke-AzJson ad sp list --filter "appId eq '$clientAppId'") 'sdlc-client service principal' } else { $null }
if (-not $clientSp) {
    Invoke-Change 'create service principal for sdlc-client' { Invoke-AzJson ad sp create --id $clientAppId } | Out-Null
}

Invoke-Change 'grant tenant-wide admin consent for sdlc-client' {
    for ($i = 1; $i -le 4; $i++) {   # new service principals can take a few seconds to replicate
        try { Invoke-Az ad app permission admin-consent --id $clientAppId | Out-Null; return }
        catch { if ($i -eq 4) { throw }; Start-Sleep -Seconds 10 }
    }
} | Out-Null

$ClientSecret = $null
$hasSecret = $client -and @($client.passwordCredentials).Count -gt 0
if ($NewClientSecret -or -not $hasSecret) {
    $ClientSecret = Invoke-Change 'create client secret for sdlc-client (1 year)' {
        (Invoke-AzJson ad app credential reset --id $clientAppId --display-name oauth2-proxy --years 1 --append).password
    }
} else {
    Write-Host '  client secret exists (pass -NewClientSecret to create another)'
}

# ---------------------------------------------------------------- 4. output
Write-Host "`n[4] Values" -ForegroundColor Green
$envValues = [ordered]@{
    ENTRA_TENANT_ID     = $TenantId
    ENTRA_API_CLIENT_ID = $apiAppId
    ENTRA_CLIENT_ID     = $clientAppId
}
if ($ClientSecret) { $envValues.ENTRA_CLIENT_SECRET = $ClientSecret }
$envValues.GetEnumerator() | ForEach-Object {
    $shown = if ($_.Key -eq 'ENTRA_CLIENT_SECRET') { '<hidden; written to .env with -WriteLocalFiles>' } else { $_.Value }
    Write-Host "  $($_.Key)=$shown"
}
if ($EffectiveUri -ne "api://$apiAppId") {
    Write-Warning "identifier URI is ${EffectiveUri}: change the second 'audience' entry in config/platform.yaml to it"
}

if ($WriteLocalFiles -and -not $DryRun) {
    $envPath = Join-Path $RepoRoot '.env'
    $envText = [IO.File]::ReadAllText($envPath)
    foreach ($kv in $envValues.GetEnumerator()) {
        $line = "$($kv.Key)=$($kv.Value)"
        if ($envText -match "(?m)^$($kv.Key)=.*$") { $envText = $envText -replace "(?m)^$($kv.Key)=.*$", $line }
        else { $envText = $envText.TrimEnd() + "`n$line`n" }
    }
    [IO.File]::WriteAllText($envPath, $envText, (New-Object Text.UTF8Encoding $false))
    Write-Host "  updated $envPath"

    $groupsPath = Join-Path $RepoRoot 'config\env\local\groups.yaml'   # git-ignored
    if (-not (Test-Path $groupsPath)) { Copy-Item "$groupsPath.example" $groupsPath }
    $yaml = [IO.File]::ReadAllText($groupsPath)
    foreach ($alias in $GroupIds.Keys) {
        $yaml = $yaml -replace "(?m)^(\s*$([regex]::Escape($alias)):\s*\{\s*id:\s*`")[^`"]*(`")", "`${1}$($GroupIds[$alias])`${2}"
    }
    [IO.File]::WriteAllText($groupsPath, $yaml, (New-Object Text.UTF8Encoding $false))
    Write-Host "  updated $groupsPath"
} elseif ($ClientSecret -and -not $DryRun) {
    Write-Host "  ENTRA_CLIENT_SECRET=$ClientSecret   <- copy into .env now; it is not shown again" -ForegroundColor Yellow
}

Write-Host "`nNext: uv run --env-file .env sdlc-config validate --env local" -ForegroundColor Green
