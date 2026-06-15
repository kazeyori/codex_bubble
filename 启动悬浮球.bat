@echo off
cd /d "%~dp0"
set CODEX_USAGE_SOURCE=codex_sessions
start "" /min pythonw "codex_usage_daemon.py"
start "" pythonw "floating_info_ball.py"
