@echo off
REM FET Measurement GUI Launcher
REM This script launches the FET measurement application

echo Starting FET Measurement GUI...
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher
    pause
    exit /b 1
)

REM Check if required packages are installed
echo Checking dependencies...
python -c "import numpy, pandas, matplotlib, pyvisa, tkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Some required packages are missing
    echo Installing required packages...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Failed to install packages. Please install manually:
        echo pip install -r requirements.txt
        pause
        exit /b 1
    )
)

REM Launch the application
echo Launching FET Measurement GUI...
echo.
python FET_Measurement_GUI.py

if %errorlevel% neq 0 (
    echo.
    echo Application exited with error code %errorlevel%
    pause
)