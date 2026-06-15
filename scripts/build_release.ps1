$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $PSCommandPath
if ([string]::IsNullOrWhiteSpace($scriptDir)) {
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$root = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$work = Join-Path $env:TEMP ("codex_bubble_release_" + $PID)
$stage = Join-Path $work "app"
$installerStage = Join-Path $work "installer"
$version = (Get-Content -LiteralPath (Join-Path $root "VERSION") -Raw).Trim()
$releaseDir = Join-Path $root "releases"
$payloadZip = Join-Path $installerStage "codex-bubble-payload.zip"
$installerExe = Join-Path $releaseDir "codex-bubble-setup-v$version.exe"
$starterName = [string]::Concat([char[]](21551,21160,24748,28014,29699,46,98,97,116))

if (Test-Path -LiteralPath $work) {
  Remove-Item -LiteralPath $work -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stage | Out-Null
New-Item -ItemType Directory -Force -Path $installerStage | Out-Null
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

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

if (Test-Path -LiteralPath $installerExe) {
  Remove-Item -LiteralPath $installerExe -Force
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($stage, $payloadZip)

Copy-Item -LiteralPath (Join-Path $root "scripts\installer\install.ps1") -Destination $installerStage -Force
$cscCandidates = @(
  (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
  (Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe")
) | Where-Object { Test-Path -LiteralPath $_ }
if ($cscCandidates.Count -eq 0) {
  throw "C# compiler not found. Expected .NET Framework csc.exe."
}

$bootstrapper = Join-Path $root "scripts\installer\InstallerBootstrapper.cs"
$installScriptPath = Join-Path $installerStage "install.ps1"
& $cscCandidates[0] `
  /nologo `
  /target:winexe `
  /out:$installerExe `
  /reference:System.Windows.Forms.dll `
  /resource:$payloadZip,codex-bubble-payload.zip `
  /resource:$installScriptPath,install.ps1 `
  $bootstrapper
if ($LASTEXITCODE -ne 0) {
  throw "Installer build failed."
}

& (Join-Path $scriptDir "verify_release.ps1") -InstallerPath $installerExe -PayloadZip $payloadZip
if ($LASTEXITCODE -ne 0) {
  throw "Release verification failed."
}

Remove-Item -LiteralPath $work -Recurse -Force

Write-Host "Built installer:"
Write-Host $installerExe
