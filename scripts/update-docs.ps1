# Regenerate API documentation artifacts (OpenAPI + TypeScript types).
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $RepoRoot
try {
    python scripts/export_openapi.py
    Push-Location web
    try {
        npm run generate:api-types
    } finally {
        Pop-Location
    }
    Write-Host ""
    Write-Host "Done. Commit docs/api/openapi.json and web/src/lib/api.generated.ts if changed."
} finally {
    Pop-Location
}
