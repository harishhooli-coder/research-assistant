# Deploy the Next.js web UI to Vercel.
#
# Prerequisites:
#   - Vercel CLI: npm i -g vercel   (or use npx vercel)
#   - vercel login (once)
#   - Fly API already deployed
#
# Usage:
#   .\scripts\deploy-vercel.ps1 -ApiUrl https://research-api.fly.dev
#   .\scripts\deploy-vercel.ps1   # reads NEXT_PUBLIC_API_URL from web/.env.local

param(
    [string]$ApiUrl,
    [string]$EnvFile = ".env.local"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Web = Join-Path $Root "web"
$EnvPath = Join-Path $Web $EnvFile

function Read-DotEnv([string]$Path) {
    $vars = @{}
    if (-not (Test-Path $Path)) { return $vars }
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

function Get-Vercel {
    if (Get-Command vercel -ErrorAction SilentlyContinue) { return "vercel" }
    return "npx --yes vercel"
}

$envVars = Read-DotEnv $EnvPath
if (-not $ApiUrl) {
    $ApiUrl = $envVars["NEXT_PUBLIC_API_URL"]
}
if (-not $ApiUrl) {
    throw "Pass -ApiUrl or set NEXT_PUBLIC_API_URL in web/$EnvFile"
}

$deployKeys = @(
    "NEXT_PUBLIC_API_URL",
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
    "CLERK_SECRET_KEY",
    "NEXT_PUBLIC_CLERK_SIGN_IN_URL",
    "NEXT_PUBLIC_CLERK_SIGN_UP_URL",
    "NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL",
    "NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL"
)

$envVars["NEXT_PUBLIC_API_URL"] = $ApiUrl
$envArgs = @()
foreach ($key in $deployKeys) {
    if ($envVars.ContainsKey($key) -and -not [string]::IsNullOrWhiteSpace($envVars[$key])) {
        $escaped = $envVars[$key] -replace '"', '\"'
        $envArgs += "--env"
        $envArgs += "${key}=$escaped"
        $envArgs += "--build-env"
        $envArgs += "${key}=$escaped"
    }
}

$vercel = Get-Vercel
Write-Host "Checking Vercel login..."
Invoke-Expression "$vercel whoami" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Not logged in. Run: npx vercel login"
}

Set-Location $Web
Write-Host "Deploying web UI to Vercel (production)..."
$cmd = "$vercel deploy --prod --yes " + ($envArgs -join " ")
Invoke-Expression $cmd
if ($LASTEXITCODE -ne 0) {
    throw "Vercel deploy failed (exit $LASTEXITCODE)"
}

Write-Host ""
Write-Host "Web UI deployed. Set CORS on Fly to your Vercel URL:"
Write-Host "  fly secrets set CORS_ALLOW_ORIGINS=https://<your-vercel-domain> --config fly/api/fly.toml"
