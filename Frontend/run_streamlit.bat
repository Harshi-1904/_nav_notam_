@echo off
REM Pakistan NAVAREA IX GIS Real-Time Agent - Streamlit Frontend Launcher (Windows)
REM This script sets up and runs the Streamlit frontend

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo Pakistan NAVAREA IX - Streamlit Frontend
echo ============================================================
echo.

REM Find Python interpreter
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
    echo Install Python 3.9+ or create a virtual environment.
    pause
    exit /b 1
)

echo [1/4] Python detected:
"%PYTHON_EXE%" --version

REM Activate virtual environment if using one
echo.
echo [2/4] Preparing environment...
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

REM Install dependencies
echo.
echo [3/4] Installing Streamlit dependencies...
"%PYTHON_EXE%" -m pip install -q -r streamlit_requirements.txt
if errorlevel 1 echo Dependencies install skipped or failed; continuing with existing packages.

REM Create .streamlit directory if it doesn't exist
echo.
echo [4/4] Configuring Streamlit...
if not exist ".streamlit" mkdir .streamlit
if not exist ".streamlit\secrets.toml" (
    echo api_url = "http://localhost:8000" > .streamlit\secrets.toml
    echo refresh_interval = 60 >> .streamlit\secrets.toml
    echo Created default .streamlit\secrets.toml
)

REM Run Streamlit app
echo.
echo ============================================================
echo Starting Streamlit Frontend...
echo.
echo The dashboard will open at: http://localhost:8501
echo API Backend should be running at: http://localhost:8000
echo.
echo Press Ctrl+C to stop
echo ============================================================
echo.

"%PYTHON_EXE%" -m streamlit run streamlit_app.py --client.toolbarMode=viewer

pause
