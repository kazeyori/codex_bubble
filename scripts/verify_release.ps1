$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $PSCommandPath
if ([string]::IsNullOrWhiteSpace($scriptDir)) {
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$root = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$version = (Get-Content -LiteralPath (Join-Path $root "VERSION") -Raw).Trim()
$zipPath = Join-Path $root "releases\codex-bubble-v$version.zip"
$starterName = [string]::Concat([char[]](21551,21160,24748,28014,29699,46,98,97,116))

Write-Host "Checking Python syntax..."
$pythonFiles = @(
  "src\codex_bubble\runtime_paths.py",
  "src\codex_bubble\floating_info_ball.py",
  "src\codex_bubble\codex_usage_fetcher.py",
  "src\codex_bubble\codex_usage_daemon.py"
) | ForEach-Object { Join-Path $root $_ }
& python -m py_compile @pythonFiles
if ($LASTEXITCODE -ne 0) {
  throw "Python syntax check failed."
}

Write-Host "Checking module imports..."
& python -c "import sys; sys.path.insert(0, r'$root\src\codex_bubble'); import runtime_paths, codex_usage_fetcher, codex_usage_daemon, floating_info_ball; print('imports ok')"
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
  ".github\workflows\release.yml",
  "src\codex_bubble\runtime_paths.py",
  "docs\assets\preview-chip-five-hour.png",
  "docs\assets\preview-chip-weekly.png",
  "docs\assets\preview-panel.png"
)
foreach ($file in $requiredFiles) {
  $path = Join-Path $root $file
  if (!(Test-Path -LiteralPath $path)) {
    throw "Missing required file: $file"
  }
}

Write-Host "Checking release package..."
if (!(Test-Path -LiteralPath $zipPath)) {
  throw "Release package not found: $zipPath"
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($zipPath)
try {
  $entries = @($archive.Entries | ForEach-Object { $_.FullName.Replace("/", "\") })
  $requiredEntries = @(
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "VERSION",
    $starterName,
    "src\codex_bubble\runtime_paths.py",
    "src\codex_bubble\floating_info_ball.py",
    "src\codex_bubble\codex_usage_fetcher.py",
    "src\codex_bubble\codex_usage_daemon.py",
    "docs\assets\preview-chip-five-hour.png",
    "docs\assets\preview-chip-weekly.png",
    "docs\assets\preview-panel.png"
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

Write-Host "Release verification passed for v$version."
