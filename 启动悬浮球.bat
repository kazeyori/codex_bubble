@echo off
cd /d "%~dp0"
start "" /min pythonw "src\codex_bubble\codex_usage_daemon.py"
start "" pythonw "src\codex_bubble\floating_info_ball.py"
