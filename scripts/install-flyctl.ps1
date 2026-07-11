# Download flyctl into .tools/ (repo-local, not committed).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Tools = Join-Path $Root ".tools"
New-Item -ItemType Directory -Force -Path $Tools | Out-Null

$release = Invoke-RestMethod -Uri "https://api.github.com/repos/superfly/flyctl/releases/latest"
$asset = $release.assets | Where-Object { $_.name -eq "flyctl_0.4.69_Windows_x86_64.zip" -or $_.name -match "Windows_x86_64\.zip$" } | Select-Object -First 1
if (-not $asset) { throw "Could not find flyctl Windows release asset." }

$zip = Join-Path $Tools "flyctl.zip"
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $Tools -Force
Remove-Item $zip

$exe = Get-ChildItem -Path $Tools -Recurse -Filter "flyctl.exe" | Select-Object -First 1
if (-not $exe) { throw "flyctl.exe not found after extract." }
Copy-Item $exe.FullName (Join-Path $Tools "flyctl.exe") -Force
Write-Host "Installed: $(Join-Path $Tools 'flyctl.exe')"
& (Join-Path $Tools "flyctl.exe") version
