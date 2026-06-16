param(
  [string]$InstallerPath = "",
  [string]$PayloadZip = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $PSCommandPath
if ([string]::IsNullOrWhiteSpace($scriptDir)) {
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$root = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$version = (Get-Content -LiteralPath (Join-Path $root "VERSION") -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($InstallerPath)) {
  $InstallerPath = Join-Path $root "releases\codex-bubble-setup-v$version.exe"
}
$starterName = "启动悬浮球.bat"
$uninstallerName = "卸载悬浮球.bat"

Write-Host "Checking Python syntax..."
$pythonFiles = @(
  "src\codex_bubble\runtime_paths.py",
  "src\codex_bubble\single_instance.py",
  "src\codex_bubble\update_checker.py",
  "src\codex_bubble\floating_info_ball.py",
  "src\codex_bubble\codex_usage_fetcher.py",
  "src\codex_bubble\codex_usage_daemon.py"
) | ForEach-Object { Join-Path $root $_ }
& python -m py_compile @pythonFiles
if ($LASTEXITCODE -ne 0) {
  throw "Python syntax check failed."
}

Write-Host "Checking module imports..."
& python -c "import sys; sys.path.insert(0, r'$root\src\codex_bubble'); import runtime_paths, single_instance, update_checker, codex_usage_fetcher, codex_usage_daemon, floating_info_ball; print('imports ok')"
if ($LASTEXITCODE -ne 0) {
  throw "Python import check failed."
}

foreach ($path in @(Get-ChildItem -LiteralPath $root -Recurse -Force -Directory -Filter "__pycache__")) {
  Remove-Item -LiteralPath $path.FullName -Recurse -Force
}

Write-Host "Checking required files..."
$requiredFiles = @(
  "README.md",
  "AGENTS.md",
  "CHANGELOG.md",
  "VERSION",
  $starterName,
  $uninstallerName,
  ".github\workflows\release.yml",
  "src\codex_bubble\runtime_paths.py",
  "src\codex_bubble\single_instance.py",
  "src\codex_bubble\update_checker.py",
  "scripts\installer\install.bat",
  "scripts\installer\install.ps1",
  "scripts\installer\InstallerBootstrapper.cs",
  "scripts\uninstall_app.ps1",
  "docs\assets\codex-bubble.ico",
  "docs\assets\preview-chip-five-hour.png",
  "docs\assets\preview-chip-weekly.png",
  "docs\assets\preview-panel.png",
  "docs\assets\preview-update-badge.png",
  "docs\assets\preview-update-panel.png",
  "docs\assets\preview-update-tray-menu.png"
)
foreach ($file in $requiredFiles) {
  $path = Join-Path $root $file
  if (!(Test-Path -LiteralPath $path)) {
    throw "Missing required file: $file"
  }
}

Write-Host "Checking installer..."
if (!(Test-Path -LiteralPath $InstallerPath)) {
  throw "Installer not found: $InstallerPath"
}
$installerInfo = Get-Item -LiteralPath $InstallerPath
if ($installerInfo.Extension -ne ".exe" -or $installerInfo.Length -lt 30000) {
  throw "Installer does not look valid: $InstallerPath"
}

$assembly = [Reflection.Assembly]::LoadFile($installerInfo.FullName)
$resourceNames = @($assembly.GetManifestResourceNames())
foreach ($resourceName in @("install.ps1", "codex-bubble-payload.zip")) {
  if ($resourceNames -notcontains $resourceName) {
    throw "Installer missing embedded resource: $resourceName"
  }
}

if ([string]::IsNullOrWhiteSpace($PayloadZip)) {
  Write-Host "Payload zip not supplied; skipped payload entry inspection."
  Write-Host "Release verification passed for v$version."
  exit 0
}

Write-Host "Checking installer payload..."
if (!(Test-Path -LiteralPath $PayloadZip)) {
  throw "Installer payload not found: $PayloadZip"
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($PayloadZip)
try {
  $entries = @($archive.Entries | ForEach-Object { $_.FullName.Replace("/", "\") })
  $requiredEntries = @(
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "VERSION",
    $starterName,
    $uninstallerName,
    "src\codex_bubble\runtime_paths.py",
    "src\codex_bubble\single_instance.py",
    "src\codex_bubble\update_checker.py",
    "src\codex_bubble\floating_info_ball.py",
    "src\codex_bubble\codex_usage_fetcher.py",
    "src\codex_bubble\codex_usage_daemon.py",
    "docs\assets\preview-chip-five-hour.png",
    "docs\assets\preview-chip-weekly.png",
    "docs\assets\preview-panel.png",
    "docs\assets\preview-update-badge.png",
    "docs\assets\preview-update-panel.png",
    "docs\assets\preview-update-tray-menu.png",
    "docs\assets\codex-bubble.ico",
    "scripts\uninstall_app.ps1"
  )
  foreach ($entry in $requiredEntries) {
    if ($entries -notcontains $entry) {
      throw "Release package missing entry: $entry"
    }
  }

  foreach ($entry in $entries) {
    if (
      $entry -match '(^|\\)\.git(\\|$)' -or
      $entry -match '(^|\\)data(\\|$)' -or
      $entry -match '(^|\\)logs(\\|$)' -or
      $entry -match '__pycache__' -or
      $entry -match '(^|\\)scripts\\dev_' -or
      $entry -match '\.log$' -or
      $entry -match 'codex_usage_data\.json$'
    ) {
      throw "Release package contains forbidden entry: $entry"
    }
  }
}
finally {
  $archive.Dispose()
}

$testRoot = Join-Path $env:TEMP ("codex_bubble_install_verify_" + $PID)
$testInstall = Join-Path $testRoot "install"
try {
  New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
  $env:CODEX_BUBBLE_INSTALL_ROOT = $testInstall
  $installerProcess = Start-Process -FilePath $InstallerPath -ArgumentList "/quiet", "/nolaunch" -Wait -PassThru
  if ($installerProcess.ExitCode -ne 0) {
    throw "Installer executable smoke test failed with exit code $($installerProcess.ExitCode)."
  }
  foreach ($file in @(
    $starterName,
    $uninstallerName,
    "src\codex_bubble\floating_info_ball.py",
    "src\codex_bubble\codex_usage_daemon.py",
    "docs\assets\codex-bubble.ico",
    "scripts\uninstall_app.ps1",
    "VERSION"
  )) {
    if (!(Test-Path -LiteralPath (Join-Path $testInstall $file))) {
      throw "Installer executable smoke test missing installed file: $file"
    }
  }
  & powershell -NoProfile -File (Join-Path $testInstall "scripts\uninstall_app.ps1") -InstallRoot $testInstall -NoPrompt -Quiet
  if ($LASTEXITCODE -ne 0) {
    throw "Uninstaller smoke test failed."
  }
  for ($attempt = 0; $attempt -lt 20; $attempt++) {
    if (!(Test-Path -LiteralPath $testInstall)) {
      break
    }
    Start-Sleep -Milliseconds 250
  }
  if (Test-Path -LiteralPath $testInstall) {
    throw "Uninstaller smoke test did not remove install directory."
  }
}
finally {
  Remove-Item Env:\CODEX_BUBBLE_INSTALL_ROOT -ErrorAction SilentlyContinue
  if (Test-Path -LiteralPath $testRoot) {
    Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}

Write-Host "Release verification passed for v$version."
