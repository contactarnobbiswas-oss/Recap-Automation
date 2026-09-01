@echo off
title Recap Automation Studio
echo Starting Recap Automation Web App...
cd /d "%~dp0backend"

pip install -r requirements.txt >nul 2>&1

echo.
echo Launching Recap Automation Web Dashboard at http://127.0.0.1:8000 ...
start http://127.0.0.1:8000

python main.py
pause
