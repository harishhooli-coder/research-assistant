# Deploy the FastAPI API layer to Vercel (Python serverless).
#
# Prerequisites:
#   npx vercel login
#   .env with Neon DATABASE_URL, cloud REDIS_URL (Upstash — not localhost),
#   NVIDIA_API_KEY, TAVILY_API_KEY
#
# Limitations:
#   - arq worker does NOT run on Vercel; POST /research enqueues jobs but they
#     won't run until you deploy the worker elsewhere (see render.yaml).
#   - SSE /research/{id}/stream needs Vercel Pro for >10s connections.
#
# Usage (from repo root):
#   .\scripts\deploy-vercel-api.ps1

param(
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Get-Vercel {
    if (Get-Command vercel -ErrorAction SilentlyContinue) {
        return "vercel"
    }
    return "npx --yes vercel"
}

function Read-DotEnv([string]$Path) {
    $vars = @{}
    if (-not (Test-Path $Path)) {
        throw "Missing $Path — copy .env.example and fill in production values."
    }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
        $eq = $trimmed.IndexOf("=")
        if ($eq -lt 1) { continue }
        $key = $trimmed.Substring(0, $eq).Trim()
        $value = $trimmed.Substring($eq + 1).Trim()
        if ($value.StartsWith('"') -and $value.EndsWith('"')) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $vars[$key] = $value
    }
    return $vars
}

$envVars = Read-DotEnv (Join-Path $Root $EnvFile)

$required = @(
    "DATABASE_URL",
    "REDIS_URL",
    "NVIDIA_API_KEY",
    "TAVILY_API_KEY"
)
foreach ($key in $required) {
    if (-not $envVars.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envVars[$key])) {
        throw "Missing required env var: $key in $EnvFile"
    }
}

$redis = $envVars["REDIS_URL"]
if ($redis -match "localhost|127\.0\.0\.1") {
    throw @"
REDIS_URL points to localhost — Vercel cannot reach your machine.
Use a cloud Redis URL (e.g. Upstash: https://upstash.com) and update $EnvFile.
"@
}

if ($envVars["DATABASE_URL"] -match "sqlite") {
    throw "DATABASE_URL must be Neon Postgres (postgresql+asyncpg://...), not SQLite."
}

$vercel = Get-Vercel
Write-Host "Checking Vercel login..."
Invoke-Expression "$vercel whoami" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Not logged in. Run: npx vercel login"
}

$deployKeys = @(
    "LLM_PROVIDER",
    "NVIDIA_API_KEY",
    "NVIDIA_MODEL",
    "NVIDIA_BASE_URL",
    "TAVILY_API_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "CORS_ALLOW_ORIGINS",
    "MAX_SUPERVISOR_STEPS",
    "MAX_CONTEXT_TOKENS",
    "MAX_FETCH_CHARS"
)

$envArgs = @()
foreach ($key in $deployKeys) {
    if ($envVars.ContainsKey($key) -and -not [string]::IsNullOrWhiteSpace($envVars[$key])) {
        $escaped = $envVars[$key] -replace '"', '\"'
        $envArgs += "--env"
        $envArgs += "${key}=$escaped"
    }
}

Write-Host "Deploying API to Vercel (production)..."
$cmd = "$vercel deploy --prod --yes " + ($envArgs -join " ")
Invoke-Expression $cmd
if ($LASTEXITCODE -ne 0) {
    throw "Vercel deploy failed (exit $LASTEXITCODE)"
}

Write-Host ""
Write-Host "API deployed. Verify: curl https://<your-deployment>/health"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Run the arq worker on Render/local so queued jobs execute."
Write-Host "  2. Point your frontend NEXT_PUBLIC_API_URL to the Vercel API URL."
Write-Host "  3. Set CORS_ALLOW_ORIGINS to your frontend origin if not using *."
