# Deploy the full Research Assistant app to Vercel.
#
# Creates two Vercel projects:
#   1. research-assistant-api  (FastAPI, repo root)
#   2. research-assistant-web  (Next.js, web/)
#
# Prerequisites:
#   npx vercel login
#   .env with Neon DATABASE_URL and cloud REDIS_URL (Upstash — not localhost)
#   web/.env.local with Clerk keys
#
# Limitations:
#   - arq worker does NOT run on Vercel; deploy worker via render.yaml or locally.
#   - SSE streams need Vercel Pro for >10s connections.
#
# Usage (from repo root):
#   .\scripts\deploy-vercel-app.ps1

param(
    [string]$EnvFile = ".env",
    [string]$WebEnvFile = "web/.env.local"
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
        throw "Missing $Path"
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

$apiEnv = Read-DotEnv (Join-Path $Root $EnvFile)
$webEnv = Read-DotEnv (Join-Path $Root $WebEnvFile)

$requiredApi = @("DATABASE_URL", "REDIS_URL", "NVIDIA_API_KEY", "TAVILY_API_KEY")
foreach ($key in $requiredApi) {
    if (-not $apiEnv.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($apiEnv[$key])) {
        throw "Missing required API env var: $key in $EnvFile"
    }
}

if ($apiEnv["REDIS_URL"] -match "localhost|127\.0\.0\.1") {
    throw "REDIS_URL must be a cloud URL (e.g. Upstash), not localhost."
}

$vercel = Get-Vercel
Write-Host "Checking Vercel login..."
Invoke-Expression "$vercel whoami" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Not logged in. Run: npx vercel login"
}

$apiKeys = @(
    "LLM_PROVIDER", "NVIDIA_API_KEY", "NVIDIA_MODEL", "NVIDIA_BASE_URL",
    "TAVILY_API_KEY", "DATABASE_URL", "REDIS_URL", "CORS_ALLOW_ORIGINS"
)
$apiEnvArgs = @()
foreach ($key in $apiKeys) {
    if ($apiEnv.ContainsKey($key) -and -not [string]::IsNullOrWhiteSpace($apiEnv[$key])) {
        $apiEnvArgs += "--env"
        $apiEnvArgs += "${key}=$($apiEnv[$key])"
    }
}

Write-Host "Deploying API (production)..."
$apiCmd = "$vercel deploy --prod --yes --name research-assistant-api " + ($apiEnvArgs -join " ")
$apiUrl = Invoke-Expression $apiCmd | Select-String -Pattern "https://\S+" | ForEach-Object { $_.Matches[0].Value } | Select-Object -Last 1
if ($LASTEXITCODE -ne 0 -or -not $apiUrl) {
    throw "API deploy failed"
}
Write-Host "API URL: $apiUrl"

$webKeys = @(
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "CLERK_SECRET_KEY",
    "NEXT_PUBLIC_CLERK_SIGN_IN_URL", "NEXT_PUBLIC_CLERK_SIGN_UP_URL",
    "NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL",
    "NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL"
)
$webEnvArgs = @("--env", "NEXT_PUBLIC_API_URL=$apiUrl", "--build-env", "NEXT_PUBLIC_API_URL=$apiUrl")
foreach ($key in $webKeys) {
    if ($webEnv.ContainsKey($key) -and -not [string]::IsNullOrWhiteSpace($webEnv[$key])) {
        $webEnvArgs += "--env"
        $webEnvArgs += "${key}=$($webEnv[$key])"
        $webEnvArgs += "--build-env"
        $webEnvArgs += "${key}=$($webEnv[$key])"
    }
}

Set-Location (Join-Path $Root "web")
Write-Host "Deploying web (production)..."
$webCmd = "$vercel deploy --prod --yes --name research-assistant-web " + ($webEnvArgs -join " ")
$webUrl = Invoke-Expression $webCmd | Select-String -Pattern "https://\S+" | ForEach-Object { $_.Matches[0].Value } | Select-Object -Last 1
if ($LASTEXITCODE -ne 0 -or -not $webUrl) {
    throw "Web deploy failed"
}

Write-Host ""
Write-Host "Deployment complete."
Write-Host "  API: $apiUrl"
Write-Host "  Web: $webUrl"
Write-Host ""
Write-Host "Set CORS_ALLOW_ORIGINS=$webUrl on the API project if not using *."
Write-Host "Deploy the arq worker separately (see render.yaml) so research jobs run."
