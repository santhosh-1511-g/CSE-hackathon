@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0backend"
if exist server.py (
    py server.py
) else (
    echo Error: server.py not found in backend directory
    echo Current directory: %CD%
    pause
    exit /b 1
)
pause
