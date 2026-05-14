@echo off
title Bot Launcher
echo Killing old python processes...
taskkill /F /IM python.exe >nul 2>&1
echo Starting bot...
python main.py
pause