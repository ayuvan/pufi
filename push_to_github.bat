@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   PUFI - Push Repository to GitHub
echo   Target: https://github.com/ayuvan/pufi
echo ============================================================
echo.

:: Ensure we are in the project root directory
cd /d "%~dp0"

:: 1. Safety check: make sure git is installed and in PATH
where git >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Git is not found in PATH. Please install Git or add it to PATH.
    pause
    exit /b 1
)

:: 2. Safety check: ensure .env files are NOT staged
echo [1/5] Verifying no secrets or .env files are staged...
git status --porcelain | findstr /I "\.env$" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo.
    echo [SECURITY ALERT] A .env file is staged for commit!
    echo Push aborted to prevent leaking credentials.
    pause
    exit /b 1
)
echo       Clean. No .env files are staged.
echo.

:: 3. Configure the GitHub remote
echo [2/5] Configuring git remote 'origin'...
git remote get-url origin >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo       Updating existing origin to https://github.com/ayuvan/pufi.git
    git remote set-url origin https://github.com/ayuvan/pufi.git
) else (
    echo       Adding origin https://github.com/ayuvan/pufi.git
    git remote add origin https://github.com/ayuvan/pufi.git
)
echo.

:: 4. Rename current branch to main for standard GitHub default branch convention
echo [3/5] Ensuring default branch is 'main'...
git branch -M main
echo.

:: 5. Show status before pushing
echo [4/5] Inspecting git status...
git status -s
echo.

:: 6. Push to GitHub
echo [5/5] Pushing to https://github.com/ayuvan/pufi.git (branch: main)...
echo       If prompted, please authenticate with your GitHub credentials.
echo.
git push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo ============================================================
    echo   [SUCCESS] PUFI repository successfully pushed to GitHub!
    echo   Repository URL: https://github.com/ayuvan/pufi
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo   [NOTICE] Git push returned an error code.
    echo   Common causes:
    echo   1. GitHub authentication needed (Personal Access Token or GitHub CLI).
    echo   2. Remote repository already contains commits (try: git pull --rebase origin main).
    echo ============================================================
)

echo.
pause
