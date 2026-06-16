@echo off
setlocal
powershell -NoProfile -File "%~dp0install.ps1"
exit /b %ERRORLEVEL%
