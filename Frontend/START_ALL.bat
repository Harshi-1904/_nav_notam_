@echo off
REM Pakistan NAVAREA IX - Complete Stack Launcher (Windows)
REM Starts both backend and frontend automatically

title Pakistan NAVAREA IX - Full Stack
color 0A

cls
echo.
echo ============================================================
echo Pakistan NAVAREA IX - Full Stack Launcher
echo ============================================================
echo.
echo This script will:
echo   1. Start the FastAPI backend on port 8000
echo   2. Start the Streamlit frontend on port 8501
echo.
echo Services will be available at:
echo   - Dashboard: http://localhost:8501
echo   - Backend API: http://localhost:8000
echo   - API Docs: http://localhost:8000/docs
echo.
echo Press any key to start...
pause >nul

REM Get absolute paths
for %%A in ("%cd%") do set "BASE_DIR=%%~fA"

set BACKEND_DIR=%BASE_DIR%
set FRONTEND_DIR=%BASE_DIR%\streamlit_frontend

echo.
echo ============================================================
echo [1/2] Starting Backend (FastAPI)...
echo ============================================================
echo.

REM Check if run.bat exists
if not exist "%BACKEND_DIR%\run.bat" (
    echo ERROR: run.bat not found in %BACKEND_DIR%
    pause
    exit /b 1
)

REM Start backend in new window
start "NAVAREA IX - Backend (FastAPI)" cmd /c "cd /d %BACKEND_DIR% && python main.py --run --host 127.0.0.1 --port 8000"

REM Wait for backend to start
echo.
echo Waiting 10 seconds for backend to initialize...
timeout /t 10 /nobreak

echo.
echo ============================================================
echo [2/2] Starting Frontend (Streamlit)...
echo ============================================================
echo.

REM Check if frontend directory exists
if not exist "%FRONTEND_DIR%" (
    echo ERROR: Frontend directory not found at %FRONTEND_DIR%
    echo Please ensure streamlit_frontend folder exists in %BASE_DIR%
    pause
    exit /b 1
)

REM Start frontend in new window
start "NAVAREA IX - Frontend (Streamlit)" cmd /c "cd /d %FRONTEND_DIR% && run_streamlit.bat"

REM Wait a moment then open browser
timeout /t 5 /nobreak

echo.
echo ============================================================
echo ✓ Both services started!
echo ============================================================
echo.
echo Frontend: http://localhost:8501 (opening in browser...)
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Note: Both services are running in separate windows.
echo Close those windows to stop the services.
echo.
echo Attempting to open dashboard in browser...
echo.

REM Try to open in default browser
start http://localhost:8501

REM Wait a bit to let user see the message
timeout /t 3 /nobreak

echo.
echo To stop all services:
echo   - Close the Backend window
echo   - Close the Frontend window
echo.
echo To view logs:
echo   - Backend logs: logs/navarea_*.log
echo   - Frontend logs: In the Streamlit window
echo.

pause
