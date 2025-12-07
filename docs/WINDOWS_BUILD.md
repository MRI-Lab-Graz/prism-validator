# Building Prism Validator on Windows

This guide explains how to build the Prism Validator Windows application from source.

## Prerequisites

1. **Python 3.8 or higher** installed on your system
   - Download from: https://www.python.org/downloads/
   - Make sure to check "Add Python to PATH" during installation

2. **Git** (if cloning the repository)
   - Download from: https://git-scm.com/download/win

## Quick Start

### Option 1: Using PowerShell (Recommended)

Open PowerShell in the project directory and run:

```powershell
.\build_windows.ps1
```

### Option 2: Using Command Prompt

Open Command Prompt in the project directory and run:

```batch
build_windows.bat
```

### Option 3: Manual Build

If the automated scripts don't work, follow these steps:

1. **Create virtual environment:**
   ```batch
   python -m venv .venv
   ```

2. **Activate virtual environment:**
   ```batch
   .venv\Scripts\activate.bat
   ```

3. **Install dependencies:**
   ```batch
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-build.txt
   ```

4. **Create survey_library folder (optional but recommended):**
   ```batch
   mkdir survey_library
   ```

5. **Build the application:**
   ```batch
   python scripts\build\build_app.py
   ```

## Output

After a successful build, you'll find the application in:
```
dist\PrismValidator\PrismValidator.exe
```

You can:
- Run it directly: `dist\PrismValidator\PrismValidator.exe`
- Double-click `PrismValidator.exe` in Windows Explorer
- Copy the entire `dist\PrismValidator\` folder to another location

## Troubleshooting

### "Python not found"
- Make sure Python is installed and added to your PATH
- Try using `py` instead of `python`: `py -3 -m venv .venv`

### "Failed to create virtual environment"
- Make sure you have write permissions in the project directory
- Try running PowerShell or Command Prompt as Administrator

### "PyInstaller build fails"
- Make sure all dependencies are installed: `pip install -r requirements-build.txt`
- Check if antivirus software is blocking PyInstaller
- Try running with `--debug` flag: `python scripts\\build\\build_app.py --debug`

### Missing icon
- The build script will automatically use the PNG logo from `static/img/MRI_Lab_Logo.png`
- If the file is missing, the build will continue without an icon

### survey_library warnings
- The `survey_library` folder is optional
- If you see a warning, the build will continue normally
- The folder is only needed if you use the survey management features

## Building for Distribution

The built application in `dist\PrismValidator\` includes:
- `PrismValidator.exe` - Main executable
- `_internal\` - Required libraries and data files
- All templates, static files, and schemas

To distribute:
1. Compress the entire `dist\PrismValidator\` folder to a ZIP file
2. Share the ZIP file with end users
3. Users can extract and run `PrismValidator.exe` without installing Python

## Platform-Specific Notes

- The Windows build uses a **folder-based distribution** (`--onedir`)
- All dependencies are packaged in the `_internal` folder
- The application runs **without a console window** (`--windowed`)
- Icon support requires a PNG or ICO file (automatically handled)

## Next Steps

After building:
- Test the application: `cd dist\PrismValidator && .\PrismValidator.exe`
- The web interface will start on `http://localhost:5001`
- Check the logs if the application doesn't start

## See Also

- [General Installation Guide](docs/INSTALLATION.md)
- [Windows Compatibility Notes](docs/WINDOWS_COMPATIBILITY.md)
- [Windows Setup Guide](docs/WINDOWS_SETUP.md)
