@echo off
setlocal enabledelayedexpansion

echo ====================================
echo DiaryML - Your Private Creative Companion
echo ====================================
echo.

REM Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python 3.10 or higher from python.org
    echo.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM Check if venv exists
if not exist "venv" (
    echo [1/3] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to create virtual environment
        echo Make sure Python 3.10+ is installed correctly
        echo.
        pause
        exit /b 1
    )
    echo ✓ Virtual environment created successfully!
    echo.
)

REM Activate virtual environment
echo [2/3] Activating virtual environment...
if not exist "venv\Scripts\activate.bat" (
    echo.
    echo ERROR: Virtual environment activation script not found
    echo Try deleting the 'venv' folder and run this script again
    echo.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo ERROR: Failed to activate virtual environment
    echo.
    pause
    exit /b 1
)
echo ✓ Virtual environment activated
echo.

REM Check if dependencies are installed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo [3/3] Installing dependencies...
    echo This will take 5-10 minutes on first run - please be patient!
    echo.

    if not exist "backend\requirements.txt" (
        echo ERROR: requirements.txt not found in backend folder
        echo Current directory: %CD%
        echo.
        pause
        exit /b 1
    )

    cd backend
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install dependencies
        echo Check the error messages above
        echo.
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo.
    echo ✓ Dependencies installed successfully!
    echo.
) else (
    echo [3/3] ✓ Dependencies already installed
    echo.
)

REM Check if backend exists
if not exist "backend\main.py" (
    echo ERROR: backend\main.py not found
    echo Current directory: %CD%
    echo.
    pause
    exit /b 1
)

REM Start the server
echo ====================================
echo Starting DiaryML Server...
echo ====================================
echo.
echo Once started, open your browser to: http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.

cd backend
python main.py

REM If we get here, server stopped
echo.
echo Server stopped.
pause
