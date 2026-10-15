@echo off
setlocal
cd /d "%~dp0"

python main.py

if errorlevel 1 (
    echo.
    echo Launch failed. Please make sure Python and requirements.txt dependencies are installed.
    pause
)
