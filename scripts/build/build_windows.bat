@echo off
REM Windows build script for Prism Validator
REM This script sets up the environment and builds the Windows executable

echo ========================================
echo Prism Validator - Windows Build Script
echo ========================================
echo.

REM 1. Check for Python
echo [1/5] Checking Python installation...
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.8+ first.
    echo Download from: https://www.python.org/downloads/
    exit /b 1
)
echo Python found.
echo.

REM 2. Create/activate virtual environment
echo [2/5] Setting up virtual environment...
if not exist .venv (
    echo Creating new virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment.
        exit /b 1
    )
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)
echo.

REM 3. Install dependencies
echo [3/5] Installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install requirements.
    exit /b 1
)
echo.

REM 4. Install PyInstaller
echo [4/5] Installing build tools...
pip install -r requirements-build.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install build requirements.
    exit /b 1
)
echo.

REM 5. Create survey_library directory if it doesn't exist (optional but prevents build errors)
if not exist survey_library (
    echo Creating empty survey_library directory...
    mkdir survey_library
    echo. > survey_library\.gitkeep
)

REM 6. Build the application
echo [5/5] Building Windows application...
python scripts\build\build_app.py
if %errorlevel% neq 0 (
    echo ERROR: Build failed.
    exit /b 1
)
echo.

echo ========================================
echo Build complete!
echo ========================================
echo.
echo Your application is in: dist\PrismValidator\
echo.
echo To run it: cd dist\PrismValidator ^&^& PrismValidator.exe
echo.
REM pause removed for automation

