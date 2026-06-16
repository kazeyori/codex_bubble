param(
  [string]$InstallRoot = "",
  [switch]$NoPrompt,
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

$displayName = "Codex 额度悬浮球"
$starterName = "启动悬浮球.bat"

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
  $InstallRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}
$InstallRoot = (Resolve-Path -LiteralPath $InstallRoot).Path.TrimEnd("\")

if (!(Test-Path -LiteralPath (Join-Path $InstallRoot $starterName)) -or
    !(Test-Path -LiteralPath (Join-Path $InstallRoot "src\codex_bubble\floating_info_ball.py"))) {
  throw "Install root does not look like CodexBubble: $InstallRoot"
}

if (!$NoPrompt -and !$Quiet) {
  $result = [System.Windows.Forms.MessageBox]::Show(
    "确定要卸载 Codex 额度悬浮球 吗？",
    $displayName,
    [System.Windows.Forms.MessageBoxButtons]::YesNo,
    [System.Windows.Forms.MessageBoxIcon]::Question
  )
  if ($result -ne [System.Windows.Forms.DialogResult]::Yes) {
    exit 0
  }
}

$processes = @()
try {
  $processes = Get-CimInstance Win32_Process -ErrorAction Stop |
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
  $processes = @()
}
foreach ($process in $processes) {
  try {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
  }
  catch {
  }
}

$shortcutNames = @(
  "$displayName.lnk",
  "卸载 Codex 额度悬浮球.lnk"
)
$shortcutFolders = @(
  [Environment]::GetFolderPath("Desktop"),
  [Environment]::GetFolderPath("Programs")
)
foreach ($folder in $shortcutFolders) {
  foreach ($name in $shortcutNames) {
    $shortcut = Join-Path $folder $name
    if (Test-Path -LiteralPath $shortcut) {
      Remove-Item -LiteralPath $shortcut -Force -ErrorAction SilentlyContinue
    }
  }
}

try {
  Remove-Item -LiteralPath $InstallRoot -Recurse -Force -ErrorAction Stop
}
catch {
  throw "卸载文件删除失败，请确认悬浮球已经退出后重试：$($_.Exception.Message)"
}

if (!$Quiet) {
  [System.Windows.Forms.MessageBox]::Show(
    "卸载完成。",
    $displayName,
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
  ) | Out-Null
}
