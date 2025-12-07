# Windows PowerShell build script for Prism Validator
# This script sets up the environment and builds the Windows executable

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Prism Validator - Windows Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check for Python
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found. Please install Python 3.8+ first." -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# 2. Create/activate virtual environment
Write-Host "[2/5] Setting up virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    Write-Host "Creating new virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Green
}
Write-Host ""

# 3. Activate virtual environment and install dependencies
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow
& .venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip --quiet

# Install requirements
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install requirements." -ForegroundColor Red
    exit 1
}
Write-Host "Dependencies installed." -ForegroundColor Green
Write-Host ""

# 4. Install PyInstaller
Write-Host "[4/5] Installing build tools..." -ForegroundColor Yellow
pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install build requirements." -ForegroundColor Red
    exit 1
}
Write-Host "Build tools installed." -ForegroundColor Green
Write-Host ""

# 5. Create survey_library directory if it doesn't exist
if (-not (Test-Path "survey_library")) {
    Write-Host "Creating empty survey_library directory..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Path "survey_library" | Out-Null
    New-Item -ItemType File -Path "survey_library\.gitkeep" | Out-Null
}

# 6. Build the application
Write-Host "[5/5] Building Windows application..." -ForegroundColor Yellow
python scripts/build/build_app.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Build failed." -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "Build complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Your application is in: dist\PrismValidator\" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run it: cd dist\PrismValidator; .\PrismValidator.exe" -ForegroundColor Yellow
Write-Host "Or double-click PrismValidator.exe in Windows Explorer" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press any key to continue..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
