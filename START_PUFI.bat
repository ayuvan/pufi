@echo off
setlocal enabledelayedexpansion

title PUFI — Enterprise Payment Coordination Platform

echo ============================================================
echo   PUFI — Enterprise Payment Coordination ^& Routing
echo   Starting Backend (port 8000) ^+ Frontend (port 5173)
echo ============================================================
echo.

REM Build the root path from this batch file's location (handles & in path)
set "ROOT=%~dp0"
REM Strip trailing backslash
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"

REM ---- Start Backend in a new window (quotes around path handle & in directory) ----
echo [1/2] Starting FastAPI backend...
start "PUFI Backend" cmd /k "cd /d "%BACKEND%" && if exist .venv\Scripts\uvicorn.exe (.venv\Scripts\uvicorn.exe main:app --reload --host 127.0.0.1 --port 8000) else (python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000)"

REM ---- Wait 4 seconds for backend to boot ----
timeout /t 4 /nobreak >nul

REM ---- Start Frontend in a new window ----
echo [2/2] Starting Vite frontend...
start "PUFI Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev"

echo.
echo ============================================================
echo   Backend  : http://localhost:8000
echo   Frontend : http://localhost:5173
echo   API Docs : http://localhost:8000/docs
echo ============================================================
echo.
echo Both servers are running in separate windows.
echo Close those windows (or press Ctrl+C in each) to stop them.
echo.
pause
endlocal
