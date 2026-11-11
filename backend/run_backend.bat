@echo off
echo Starting PUFI FastAPI Backend...
cd /d "%~dp0"
if exist .venv\Scripts\uvicorn.exe (
    .\.venv\Scripts\uvicorn.exe main:app --reload --host 127.0.0.1 --port 8000
) else (
    python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
)
pause
