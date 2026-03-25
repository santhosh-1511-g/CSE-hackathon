@echo off
cd /d "%~dp0backend"
if exist server.py (
    python server.py
) else (
    echo Error: server.py not found in backend directory
    echo Current directory: %CD%
    pause
    exit /b 1
)
pause

