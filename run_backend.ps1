Write-Host "Starting PUFI FastAPI Backend..." -ForegroundColor Cyan
Set-Location -Path "$PSScriptRoot\backend"
if (Test-Path ".\.venv\Scripts\uvicorn.exe") {
    & ".\.venv\Scripts\uvicorn.exe" main:app --reload --host 127.0.0.1 --port 8000
} else {
    python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
}
