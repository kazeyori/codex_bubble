param(
  [string]$InstallRoot = "",
  [switch]$NoPrompt,
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

$displayName = [string]::Concat([char[]](67,111,100,101,120,32,39069,24230,24748,28014,29699))
$starterName = [string]::Concat([char[]](21551,21160,24748,28014,29699,46,98,97,116))

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
    [string]::Concat([char[]](30830,23450,35201,21368,36733,32,67,111,100,101,120,32,39069,24230,24748,28014,29699,32,21527,65311)),
    $displayName,
    [System.Windows.Forms.MessageBoxButtons]::YesNo,
    [System.Windows.Forms.MessageBoxIcon]::Question
  )
  if ($result -ne [System.Windows.Forms.DialogResult]::Yes) {
    exit 0
  }
}

$processes = Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -and (
      $_.CommandLine -like "*codex_bubble*floating_info_ball.py*" -or
      $_.CommandLine -like "*codex_bubble*codex_usage_daemon.py*" -or
      $_.CommandLine -like "*CodexBubble*floating_info_ball.py*" -or
      $_.CommandLine -like "*CodexBubble*codex_usage_daemon.py*"
    )
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
  ([string]::Concat([char[]](21368,36733,32,67,111,100,101,120,32,39069,24230,24748,28014,29699,46,108,110,107)))
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

$deleteScript = Join-Path $env:TEMP ("codex_bubble_uninstall_" + $PID + ".cmd")
$escapedRoot = $InstallRoot.Replace('"', '""')
$message = [string]::Concat([char[]](21368,36733,23436,25104,12290))
if ($Quiet) {
  $content = "@echo off`r`ntimeout /t 1 /nobreak >nul`r`nrd /s /q ""$escapedRoot""`r`ndel ""%~f0""`r`n"
}
else {
  $content = "@echo off`r`ntimeout /t 1 /nobreak >nul`r`nrd /s /q ""$escapedRoot""`r`nmsg * ""$message"" >nul 2>nul`r`ndel ""%~f0""`r`n"
}
Set-Content -LiteralPath $deleteScript -Value $content -Encoding ASCII
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$deleteScript`"" -WorkingDirectory $env:TEMP -WindowStyle Hidden
