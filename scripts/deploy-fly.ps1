# Production deploy: Vercel (web) + Fly.io (API, worker, Redis, Postgres)
#
# Prerequisites:
#   1. Fly.io account + `.\.tools\flyctl.exe auth login`
#   2. Real API keys in a local `.env` (never commit)
#
# Usage (PowerShell, from repo root):
#   .\scripts\deploy-fly.ps1
#   .\scripts\deploy-vercel.ps1 -ApiUrl https://research-api.fly.dev

param(
    [string]$Region = "iad",
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Get-Fly {
    if (Get-Command fly -ErrorAction SilentlyContinue) { return "fly" }
    $local = Join-Path $Root ".tools\flyctl.exe"
    if (Test-Path $local) { return $local }
    throw "flyctl not found. Run scripts/install-flyctl.ps1"
}

function Read-DotEnv([string]$Path) {
    $vars = @{}
    if (-not (Test-Path $Path)) { return $vars }
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
        $name, $value = $_ -split '=', 2
        $vars[$name.Trim()] = $value.Trim()
    }
    return $vars
}

function Ensure-FlyApp([string]$Fly, [string]$AppName) {
    $apps = & $Fly apps list --json | ConvertFrom-Json
    $exists = $apps | Where-Object { $_.Name -eq $AppName }
    if (-not $exists) {
        Write-Host "Creating Fly app $AppName..."
        & $Fly apps create $AppName --org personal
    }
}

$fly = Get-Fly
$envVars = Read-DotEnv $EnvFile

if (-not $envVars["NVIDIA_API_KEY"] -or $envVars["NVIDIA_API_KEY"].EndsWith("...") -or $envVars["NVIDIA_API_KEY"].Length -lt 10) {
    throw "Set a real NVIDIA_API_KEY in $EnvFile before deploying."
}
if (-not $envVars["TAVILY_API_KEY"] -or $envVars["TAVILY_API_KEY"].Length -lt 20) {
    Write-Warning "TAVILY_API_KEY looks incomplete - web search will fail until you update Fly secrets."
}

Write-Host "==> Creating Fly apps (if needed)..."
Ensure-FlyApp $fly "research-redis"
Ensure-FlyApp $fly "research-api"
Ensure-FlyApp $fly "research-worker"

Write-Host "==> Deploying Redis..."
Push-Location (Join-Path $Root "fly\redis")
try {
    $vols = & $fly volumes list --app research-redis --json | ConvertFrom-Json
    if (-not $vols) {
        & $fly volumes create redis_data --region $Region --size 1 --app research-redis --yes
    }
    & $fly deploy --config fly.toml --remote-only
} finally {
    Pop-Location
}

$dbUrl = $envVars["DATABASE_URL"]
if ($dbUrl -match "localhost|^\s*$") {
    Write-Host "==> Creating Fly Postgres (skip if cluster already exists)..."
    $pg = & $fly postgres list --json | ConvertFrom-Json
    $pgExists = $pg | Where-Object { $_.Name -eq "research-db" }
    if (-not $pgExists) {
        & $fly postgres create --name research-db --region $Region --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 1 --org personal
    }
    & $fly postgres attach research-db --app research-api
    & $fly postgres attach research-db --app research-worker
}

$secretPairs = @(
    "LLM_PROVIDER=$(if ($envVars['LLM_PROVIDER']) { $envVars['LLM_PROVIDER'] } else { 'nvidia' })"
    "NVIDIA_API_KEY=$($envVars['NVIDIA_API_KEY'])"
    "NVIDIA_MODEL=$(if ($envVars['NVIDIA_MODEL']) { $envVars['NVIDIA_MODEL'] } else { 'meta/llama-3.3-70b-instruct' })"
    "NVIDIA_BASE_URL=$(if ($envVars['NVIDIA_BASE_URL']) { $envVars['NVIDIA_BASE_URL'] } else { 'https://integrate.api.nvidia.com/v1' })"
    "TAVILY_API_KEY=$($envVars['TAVILY_API_KEY'])"
    "REDIS_URL=redis://research-redis.internal:6379"
)
if ($envVars["CORS_ALLOW_ORIGINS"]) { $secretPairs += "CORS_ALLOW_ORIGINS=$($envVars['CORS_ALLOW_ORIGINS'])" }
if ($envVars["DATABASE_URL"] -and $envVars["DATABASE_URL"] -notmatch "localhost") {
    $secretPairs += "DATABASE_URL=$($envVars['DATABASE_URL'])"
}

Write-Host "==> Setting API secrets..."
& $fly secrets set @secretPairs --config fly/api/fly.toml

Write-Host "==> Deploying API..."
& $fly deploy --config fly/api/fly.toml --dockerfile Dockerfile --remote-only

Write-Host "==> Setting worker secrets..."
& $fly secrets set @secretPairs --config fly/worker/fly.toml

Write-Host "==> Deploying worker..."
& $fly deploy --config fly/worker/fly.toml --dockerfile Dockerfile --remote-only

Write-Host "==> Running migrations..."
& $fly ssh console --app research-api --command "alembic upgrade head"

$apiUrl = "https://research-api.fly.dev"
Write-Host ""
Write-Host "Backend deployed: $apiUrl"
Write-Host "Next: .\scripts\deploy-vercel.ps1 -ApiUrl $apiUrl"
