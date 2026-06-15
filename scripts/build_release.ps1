$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $PSCommandPath
if ([string]::IsNullOrWhiteSpace($scriptDir)) {
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$root = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$stage = Join-Path $env:TEMP "codex_bubble_release_stage"
$version = (Get-Content -LiteralPath (Join-Path $root "VERSION") -Raw).Trim()
$versionedZip = Join-Path $root "releases\codex-bubble-v$version.zip"
$legacyZip = Join-Path $root "releases\codex-floating-info-ball-share.zip"
$starterName = [string]::Concat([char[]](21551,21160,24748,28014,29699,46,98,97,116))

if (Test-Path -LiteralPath $stage) {
  Remove-Item -LiteralPath $stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stage | Out-Null

foreach ($path in @(Get-ChildItem -LiteralPath $root -Recurse -Force -Directory -Filter "__pycache__")) {
  Remove-Item -LiteralPath $path.FullName -Recurse -Force
}

foreach ($item in @(
  "src",
  "config",
  "scripts",
  "docs",
  "README.md",
  "AGENTS.md",
  "CHANGELOG.md",
  "VERSION",
  $starterName
)) {
  Copy-Item -LiteralPath (Join-Path $root $item) -Destination $stage -Recurse -Force
}

foreach ($name in @("data", "logs", "__pycache__", ".pytest_cache")) {
  foreach ($path in @(Get-ChildItem -LiteralPath $stage -Recurse -Force -Directory -Filter $name)) {
    Remove-Item -LiteralPath $path.FullName -Recurse -Force
  }
}
foreach ($path in @(Get-ChildItem -LiteralPath $stage -Recurse -Force -File)) {
  if (
    $path.Extension -in @(".pyc", ".pyo", ".log", ".tmp", ".bak") -or
    $path.Name -eq "codex_usage_data.json"
  ) {
    Remove-Item -LiteralPath $path.FullName -Force
  }
}

foreach ($zip in @($versionedZip, $legacyZip)) {
  if (Test-Path -LiteralPath $zip) {
    Remove-Item -LiteralPath $zip -Force
  }
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  [IO.Compression.ZipFile]::CreateFromDirectory($stage, $zip)
}

Remove-Item -LiteralPath $stage -Recurse -Force

& (Join-Path $scriptDir "verify_release.ps1")
if ($LASTEXITCODE -ne 0) {
  throw "Release verification failed."
}

Write-Host "Built release package:"
Write-Host $versionedZip
