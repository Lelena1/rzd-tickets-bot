@echo off
cd /d "%~dp0"
"C:\Program Files\Python312\python.exe" -m bot.main >> bot_autostart.log 2>&1
