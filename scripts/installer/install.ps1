param(
  [switch]$NoLaunch,
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

$appName = "CodexBubble"
$displayName = [string]::Concat([char[]](67,111,100,101,120,32,39069,24230,24748,28014,29699))
$starterName = [string]::Concat([char[]](21551,21160,24748,28014,29699,46,98,97,116))
$uninstallerName = [string]::Concat([char[]](21368,36733,24748,28014,29699,46,98,97,116))
$uninstallShortcutName = [string]::Concat([char[]](21368,36733,32,67,111,100,101,120,32,39069,24230,24748,28014,29699,46,108,110,107))
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
  $oldProcesses = Get-CimInstance Win32_Process |
    Where-Object {
      $_.CommandLine -and (
        $_.CommandLine -like "*codex_bubble*floating_info_ball.py*" -or
        $_.CommandLine -like "*codex_bubble*codex_usage_daemon.py*" -or
        $_.CommandLine -like "*CodexBubble*floating_info_ball.py*" -or
        $_.CommandLine -like "*CodexBubble*codex_usage_daemon.py*"
      )
    }
  foreach ($process in $oldProcesses) {
    try {
      Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
    catch {
    }
  }
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
      [string]::Concat([char[]](23433,35013,23436,25104,12290,24050,21019,24314,26700,38754,21644,24320,22987,33756,21333,24555,25463,26041,24335,65292,24182,21551,21160,24748,28014,29699,12290)),
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
