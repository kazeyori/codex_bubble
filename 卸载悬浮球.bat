@echo off
cd /d "%~dp0"
powershell -NoProfile -File "scripts\uninstall_app.ps1" -InstallRoot "%~dp0"
