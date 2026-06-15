$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $PSCommandPath
if ([string]::IsNullOrWhiteSpace($scriptDir)) {
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$appDir = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "Codex Floating Info Ball Local Usage.lnk"
$starter = Join-Path $appDir "启动悬浮球.bat"

foreach ($oldName in @(
  "Codex Floating Info Ball.lnk",
  "Codex Floating Info Ball Real Usage.lnk",
  "Codex Floating Info Ball Local Usage.lnk",
  "Codex 悬浮球-本地额度同步.lnk"
)) {
  $oldPath = Join-Path $startup $oldName
  if (Test-Path -LiteralPath $oldPath) {
    Remove-Item -LiteralPath $oldPath -Force
  }
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $env:ComSpec
$shortcut.Arguments = "/c `"$starter`""
$shortcut.WorkingDirectory = $appDir
$shortcut.WindowStyle = 7
$shortcut.Description = "Start Codex floating info ball with local Codex rate-limit sync"
$shortcut.Save()

Write-Host "Startup shortcut created:"
Write-Host $shortcutPath
