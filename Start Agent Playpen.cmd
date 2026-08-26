@echo off
setlocal
title Agent Playpen Web App
cd /d "%~dp0"

set "URL=http://127.0.0.1:8765/"
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [ERROR] Virtual environment not found:
  echo   "%PY%"
  echo Create the .venv and install requirements, then run this again.
  echo.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',8765);$c.Close();exit 0}catch{exit 1}"
if not errorlevel 1 (
  echo Agent Playpen is already running - opening browser...
  start "" "%URL%"
  exit /b 0
)

echo Starting Agent Playpen web app on %URL%
echo Close this window to stop the server.
echo.

start "" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "for($i=0;$i -lt 120;$i++){try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',8765);$c.Close();Start-Process '%URL%';break}catch{Start-Sleep -Milliseconds 500}}"

"%PY%" -m uvicorn debugging.dashboard.server:app --host 127.0.0.1 --port 8765

echo.
echo Server stopped.
pause
