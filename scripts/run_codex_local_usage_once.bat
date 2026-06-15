@echo off
cd /d "%~dp0\.."
set CODEX_USAGE_SOURCE=codex_sessions
python "src\codex_bubble\codex_usage_fetcher.py"
pause
