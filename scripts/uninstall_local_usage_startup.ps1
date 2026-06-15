$ErrorActionPreference = "Stop"

$startup = [Environment]::GetFolderPath("Startup")
$shortcutNames = @(
  "Codex Floating Info Ball Local Usage.lnk",
  "Codex Floating Info Ball Real Usage.lnk",
  "Codex Floating Info Ball.lnk",
  "Codex 悬浮球-本地额度同步.lnk"
)
$removed = $false
foreach ($name in $shortcutNames) {
  $shortcutPath = Join-Path $startup $name
  if (Test-Path -LiteralPath $shortcutPath) {
    Remove-Item -LiteralPath $shortcutPath -Force
    Write-Host "Removed:"
    Write-Host $shortcutPath
    $removed = $true
  }
}
if (-not $removed) {
  Write-Host "No startup shortcut found."
}
