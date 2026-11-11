<#
.SYNOPSIS
  Idempotent Entra ID setup for the agentic SDLC platform (Stage 2).
  Works in Windows PowerShell 5.1 and PowerShell 7. Safe to re-run: finds and completes
  existing objects instead of duplicating them.

.DESCRIPTION
  Creates or updates:
    - app sdlc-mcp (API): identifier URI, access_as_user scope, v2 tokens, NO groups claim
      (membership comes from app roles only, CH-0011), app roles ($AppRoles), Azure CLI
      pre-authorized (dev testing), assignment required
    - app role assignments: user A = SDLC.User + SDLC.Payments.Member, user B = SDLC.User +
      SDLC.Platform.Member, admin = SDLC.User + SDLC.Admin, and -AppRoleUser with
      -AppRoleUserRoles. Assignments are only added; remove old ones in the portal.
    - app sdlc-client (web, for oauth2-proxy in Stage 2d): redirect URI, access_as_user
      permission + admin consent, optional client secret

  It creates no Entra groups and never deletes anything: remove old app roles (disable first),
  old assignments, GroupMember.Read.All and the groups by hand.

  Why a script: on Windows `az` is az.cmd, so every argument goes through cmd.exe. JSON
  bodies and OData filters with parentheses get mangled. This script passes JSON via
  temp files (--body @file) and avoids special characters in arguments.

.EXAMPLE
  az login --tenant <tenant> --allow-no-subscriptions
  .\scripts\entra_setup.ps1 -TestUserA ad.paul@contoso.onmicrosoft.com -TestUserB ad.b@contoso.onmicrosoft.com -DryRun
  .\scripts\entra_setup.ps1 -TestUserA ... -TestUserB ... -AdminUser <upn> -NewClientSecret -WriteLocalFiles
  .\scripts\entra_setup.ps1 -TestUserA ... -TestUserB ... -AppRoleUser <upn> -AppRoleUserRoles SDLC.User,SDLC.Platform.Member
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TestUserA,   # SDLC.User + SDLC.Payments.Member
    [Parameter(Mandatory = $true)][string]$TestUserB,   # SDLC.User + SDLC.Platform.Member
    [string]$AdminUser = '',                             # optional: SDLC.User + SDLC.Admin
    [string]$IdentifierUri = '',   # default api://<sdlc-mcp appId> (matches config/platform.yaml)
    # oauth2-proxy callbacks: local + public (Cloudflare Tunnel). Existing URIs are kept.
    [string[]]$RedirectUri = @('http://localhost:4180/oauth2/callback', 'https://app-sdlc-dev.shaheenks.co.in/oauth2/callback'),
    [switch]$NewClientSecret,   # create a new sdlc-client secret (printed once / written to .env)
    [switch]$WriteLocalFiles,   # update .env with the real IDs
    [switch]$DryRun,            # read-only: print planned changes, modify nothing
    [switch]$NoAzCliPreAuth,    # prod/enterprise: no Azure CLI pre-authorization (removes it if present)
    # optional extra user who gets these app roles assigned
    [string]$AppRoleUser = '',
    [string[]]$AppRoleUserRoles = @('SDLC.User', 'SDLC.Payments.Member')
)

$ErrorActionPreference = 'Stop'
$GraphBase = 'https://graph.microsoft.com/v1.0'
$AzCliClientId = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'   # Azure CLI (pre-authorized for dev tokens)
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Assignments = @(
    @{ User = $TestUserA; Roles = @('SDLC.User', 'SDLC.Payments.Member') },
    @{ User = $TestUserB; Roles = @('SDLC.User', 'SDLC.Platform.Member') }
)
if ($AdminUser) { $Assignments += @{ User = $AdminUser; Roles = @('SDLC.User', 'SDLC.Admin') } }
if ($AppRoleUser) { $Assignments += @{ User = $AppRoleUser; Roles = $AppRoleUserRoles } }
# App roles on sdlc-mcp: value = description. They appear in the access token's `roles` claim
# and are the only source of membership besides users.yaml (CH-0011). config/ grants them as
# `app_role: <value>`; tests/policy/test_app_roles.py checks that both lists match. Roles are
# only added or updated here, never removed (Entra needs a role disabled before it can be
# deleted: do that by hand).
$AppRoles = [ordered]@{
    'SDLC.User'              = 'SDLC viewer: knowledge search, skills, own artifacts'
    'SDLC.Admin'             = 'SDLC admin: every tool and skill'
    'SDLC.Payments.Member'   = 'Payments team member'
    'SDLC.Payments.Approver' = 'Payments team approver'
    'SDLC.Platform.Member'   = 'SDLC platform team member'
    'SDLC.Platform.Approver' = 'SDLC platform team approver'
    'SDLC.Webapp.Member'     = 'Webapp team member'
    'SDLC.Webapp.Approver'   = 'Webapp team approver'
}
foreach ($r in @($Assignments | ForEach-Object { $_.Roles })) {
    if (-not $AppRoles.Contains($r)) { throw "unknown app role $r (defined: $($AppRoles.Keys -join ', '))" }
}

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

# 1b. scope + v2 tokens, groups claim off (scope must exist before it can be pre-authorized).
#     Membership comes from app roles only (CH-0011): tokens carry no `groups` claim.
Invoke-Change 'set access_as_user scope, v2 access tokens, no groups claim' {
    Invoke-Graph PATCH "/applications/$($api.id)" @{
        api                   = $apiSettings
        groupMembershipClaims = 'None'
        optionalClaims        = @{ accessToken = @(); idToken = @(); saml2Token = @() }
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

# 1d. app roles (version-03 P2 E1): keep existing ids, add missing roles, leave other roles alone.
#     allowedMemberTypes User: users are assigned (no groups, CH-0011).
$currentRoles = @(if ($api) { $api.appRoles } else { @() })
$AppRoleIds = @{}
$desiredRoles = @()
$roleChanges = @()
foreach ($value in $AppRoles.Keys) {
    $existing = $currentRoles | Where-Object { $_.value -eq $value } | Select-Object -First 1
    $id = if ($existing) { $existing.id } else { [guid]::NewGuid().ToString() }
    $AppRoleIds[$value] = $id
    $desiredRoles += @{
        id = $id; value = $value; displayName = $value; description = $AppRoles[$value]
        allowedMemberTypes = @('User'); isEnabled = $true
    }
    if (-not $existing) { $roleChanges += "add $value" }
    elseif ($existing.description -ne $AppRoles[$value] -or -not $existing.isEnabled) { $roleChanges += "update $value" }
}
$otherRoles = @($currentRoles | Where-Object { -not $AppRoles.Contains([string]$_.value) })
if ($roleChanges.Count -eq 0) {
    Write-Host "  app roles ok: $($AppRoles.Keys -join ', ')"
} else {
    Invoke-Change "app roles on sdlc-mcp: $($roleChanges -join ', ')" {
        Invoke-Graph PATCH "/applications/$($api.id)" @{ appRoles = @($otherRoles) + @($desiredRoles) } | Out-Null
    } | Out-Null
}
if ($otherRoles.Count) { Write-Host "  other app roles kept: $(@($otherRoles | ForEach-Object { $_.value }) -join ', ')" }

# 1e. service principal with assignment required
$apiSp = if ($api) { Get-Single (Invoke-AzJson ad sp list --filter "appId eq '$apiAppId'") 'sdlc-mcp service principal' } else { $null }
if (-not $apiSp) {
    $apiSp = Invoke-Change 'create service principal for sdlc-mcp' { Invoke-AzJson ad sp create --id $apiAppId }
}
if ($apiSp -and $apiSp.appRoleAssignmentRequired) {
    Write-Host '  assignment required: ok'
} else {
    Invoke-Change 'require assignment (only assigned users can get tokens)' {
        Invoke-Graph PATCH "/servicePrincipals/$($apiSp.id)" @{ appRoleAssignmentRequired = $true } | Out-Null
    } | Out-Null
}

# ---------------------------------------------------------------- 2. app role assignments
# Only adds; remove an assignment in the portal (Enterprise apps > sdlc-mcp > Users and groups).
Write-Host "`n[2] App role assignments" -ForegroundColor Green
$assignedTo = if ($apiSp) { @((Invoke-Graph GET "/servicePrincipals/$($apiSp.id)/appRoleAssignedTo").value) } else { @() }
foreach ($a in $Assignments) {
    $u = Invoke-AzJson ad user show --id $a.User
    $have = @($assignedTo | Where-Object { $_.principalId -eq $u.id } | ForEach-Object { $_.appRoleId })
    foreach ($value in $a.Roles) {
        $roleId = $AppRoleIds[$value]
        if ($have -contains $roleId) { Write-Host "  $($a.User) has $value : ok"; continue }
        Invoke-Change "assign app role $value to $($a.User)" {
            Invoke-Graph POST "/servicePrincipals/$($apiSp.id)/appRoleAssignedTo" @{
                principalId = $u.id; resourceId = $apiSp.id; appRoleId = $roleId
            } | Out-Null
        } | Out-Null
    }
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

# Wrap in @() OUTSIDE the if: an if-expression unrolls a one-element array to a plain string,
# and string + array concatenates text instead of combining lists.
$redirects = @(if ($client) { $client.web.redirectUris } else { $RedirectUri })
# Drop malformed entries (e.g. two URIs glued together by an earlier run of this script).
$malformed = @($redirects | Where-Object { ([regex]::Matches($_, '://')).Count -ne 1 })
$validRedirects = @($redirects | Where-Object { $malformed -notcontains $_ })
$missingRedirects = @($RedirectUri | Where-Object { $validRedirects -notcontains $_ })
if ($missingRedirects.Count -eq 0 -and $malformed.Count -eq 0) { Write-Host "  redirect URIs ok: $($validRedirects -join ', ')" }
else {
    $desired = @($validRedirects) + @($missingRedirects)
    $what = "set redirect URIs: $($desired -join ', ')"
    if ($malformed.Count) { $what += " (removing malformed: $($malformed -join ', '))" }
    Invoke-Change $what {
        Invoke-Graph PATCH "/applications/$($client.id)" @{ web = @{ redirectUris = $desired } } | Out-Null
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
} elseif ($ClientSecret -and -not $DryRun) {
    Write-Host "  ENTRA_CLIENT_SECRET=$ClientSecret   <- copy into .env now; it is not shown again" -ForegroundColor Yellow
}

Write-Host "`nNext: uv run --env-file .env sdlc-config validate --env local" -ForegroundColor Green
