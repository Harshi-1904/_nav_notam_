@echo off
REM Pakistan NAVAREA IX GIS Real-Time Agent - Windows Quick Start
REM This script automates setup and running on Windows

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo Pakistan NAVAREA IX GIS Real-Time Agent
echo ============================================================
echo.

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=.venv\Scripts\python.exe"
)
if not defined PYTHON_EXE if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=venv\Scripts\python.exe"
)

if not defined PYTHON_EXE (
    for %%P in (python py) do (
        where %%P >nul 2>&1
        if not errorlevel 1 (
            %%P --version >nul 2>&1
            if not errorlevel 1 set "PYTHON_EXE=%%P"
        )
    )
)

if not defined PYTHON_EXE (
    echo ERROR: No Python interpreter found.
    echo Install Python 3.9+ or recreate the virtual environment with a valid interpreter.
    pause
    exit /b 1
)

echo [1/5] Python detected:
"%PYTHON_EXE%" --version

REM Activate virtual environment if using one
echo.
echo [2/5] Preparing environment...
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

REM Install dependencies
echo.
echo [3/5] Installing dependencies...
"%PYTHON_EXE%" -m pip install -q -r requirements.txt
if errorlevel 1 echo Dependencies install skipped or failed; continuing with existing packages.

REM Run agent
echo.
echo [4/5] Starting agent...
echo.
echo ============================================================
echo Agent starting...
echo API will be available at: http://localhost:8000
echo Documentation at: http://localhost:8000/docs
echo Press Ctrl+C to stop
echo ============================================================
echo.

"%PYTHON_EXE%" main.py --run --host 127.0.0.1 --port 8000

pause
