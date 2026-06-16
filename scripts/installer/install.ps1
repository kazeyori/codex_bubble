param(
  [switch]$NoLaunch,
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

$appName = "CodexBubble"
$displayName = "Codex 额度悬浮球"
$starterName = "启动悬浮球.bat"
$uninstallerName = "卸载悬浮球.bat"
$uninstallShortcutName = "卸载 Codex 额度悬浮球.lnk"
$installRoot = $env:CODEX_BUBBLE_INSTALL_ROOT
if ([string]::IsNullOrWhiteSpace($installRoot)) {
  $installRoot = Join-Path $env:LOCALAPPDATA "Programs\CodexBubble"
}
$scriptDir = Split-Path -Parent $PSCommandPath
$payload = Join-Path $scriptDir "codex-bubble-payload.zip"

if (!(Test-Path -LiteralPath $payload)) {
  throw "Installer payload is missing: codex-bubble-payload.zip"
}

if (!$NoLaunch) {
  $oldProcesses = @()
  try {
    $oldProcesses = Get-CimInstance Win32_Process -ErrorAction Stop |
      Where-Object {
        $_.CommandLine -and (
          $_.CommandLine -like "*codex_bubble*floating_info_ball.py*" -or
          $_.CommandLine -like "*codex_bubble*codex_usage_daemon.py*" -or
          $_.CommandLine -like "*CodexBubble*floating_info_ball.py*" -or
          $_.CommandLine -like "*CodexBubble*codex_usage_daemon.py*"
        )
      }
  }
  catch {
    $oldProcesses = @()
  }
  foreach ($process in $oldProcesses) {
    try {
      Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
      Wait-Process -Id $process.ProcessId -Timeout 5 -ErrorAction SilentlyContinue
    }
    catch {
    }
  }
  Start-Sleep -Milliseconds 500
}

$backupRoot = $null
if (Test-Path -LiteralPath $installRoot) {
  $backupRoot = "$installRoot.backup"
  if (Test-Path -LiteralPath $backupRoot) {
    Remove-Item -LiteralPath $backupRoot -Recurse -Force
  }
  Move-Item -LiteralPath $installRoot -Destination $backupRoot -Force
}

try {
  New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
  Expand-Archive -LiteralPath $payload -DestinationPath $installRoot -Force

  $starter = Join-Path $installRoot $starterName
  $uninstaller = Join-Path $installRoot $uninstallerName
  $iconPath = Join-Path $installRoot "docs\assets\codex-bubble.ico"
  if (!(Test-Path -LiteralPath $starter)) {
    throw "Installed starter file is missing."
  }
  if (!(Test-Path -LiteralPath $uninstaller)) {
    throw "Installed uninstaller file is missing."
  }

  if (!$Quiet) {
    $shortcutTargets = @(
      @{
        Path = Join-Path ([Environment]::GetFolderPath("Desktop")) "$displayName.lnk"
        Target = $starter
      },
      @{
        Path = Join-Path ([Environment]::GetFolderPath("Programs")) "$displayName.lnk"
        Target = $starter
      },
      @{
        Path = Join-Path ([Environment]::GetFolderPath("Programs")) $uninstallShortcutName
        Target = $uninstaller
      }
    )
    $shell = New-Object -ComObject WScript.Shell
    foreach ($shortcutSpec in $shortcutTargets) {
      $shortcut = $shell.CreateShortcut($shortcutSpec.Path)
      $shortcut.TargetPath = $shortcutSpec.Target
      $shortcut.WorkingDirectory = $installRoot
      if (Test-Path -LiteralPath $iconPath) {
        $shortcut.IconLocation = $iconPath
      }
      else {
        $shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,70"
      }
      $shortcut.Description = $displayName
      $shortcut.Save()
    }
  }

  if ($backupRoot -and (Test-Path -LiteralPath $backupRoot)) {
    Remove-Item -LiteralPath $backupRoot -Recurse -Force
  }

  if (!$NoLaunch) {
    Start-Process -FilePath $starter -WorkingDirectory $installRoot
  }
  if (!$Quiet) {
    [System.Windows.Forms.MessageBox]::Show(
      "安装完成。已创建桌面和开始菜单快捷方式，并启动悬浮球。",
      $displayName,
      [System.Windows.Forms.MessageBoxButtons]::OK,
      [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
  }
}
catch {
  if (Test-Path -LiteralPath $installRoot) {
    Remove-Item -LiteralPath $installRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
  if ($backupRoot -and (Test-Path -LiteralPath $backupRoot)) {
    Move-Item -LiteralPath $backupRoot -Destination $installRoot -Force
  }
  throw
}
