# Deploy the Next.js web UI to Vercel.
#
# Prerequisites:
#   - Vercel CLI: npm i -g vercel   (or use npx vercel)
#   - vercel login (once)
#   - Fly API already deployed
#
# Usage:
#   .\scripts\deploy-vercel.ps1 -ApiUrl https://research-api.fly.dev

param(
    [Parameter(Mandatory = $true)]
    [string]$ApiUrl
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Web = Join-Path $Root "web"
Set-Location $Web

if (-not (Get-Command vercel -ErrorAction SilentlyContinue)) {
    Write-Host "Using npx vercel..."
    npx --yes vercel deploy --prod `
        --env "NEXT_PUBLIC_API_URL=$ApiUrl" `
        --build-env "NEXT_PUBLIC_API_URL=$ApiUrl"
} else {
    vercel deploy --prod `
        --env "NEXT_PUBLIC_API_URL=$ApiUrl" `
        --build-env "NEXT_PUBLIC_API_URL=$ApiUrl"
}

Write-Host ""
Write-Host "Web UI deployed. Set CORS on Fly to your Vercel URL:"
Write-Host "  fly secrets set CORS_ALLOW_ORIGINS=https://<your-vercel-domain> --config fly/api/fly.toml"
