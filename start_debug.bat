@echo off
REM Xatolarni ko`rish uchun (konsol bilan ochadi)
cd /d "%~dp0src"
"%~dp0venv\Scripts\python.exe" gui.py
pause
