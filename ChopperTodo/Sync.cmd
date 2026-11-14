@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" GoogleSync.py %* >> sync.log 2>&1
) else (
  py -3 GoogleSync.py %* >> sync.log 2>&1
)
exit /b %ERRORLEVEL%
