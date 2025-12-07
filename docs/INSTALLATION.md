# Installation

Prism-Validator is designed to be easy to install on Windows, macOS, and Linux.

## Prerequisites

- **Python 3.8 or higher**: [Download Python](https://www.python.org/downloads/)
- **Git** (optional, for cloning the repository): [Download Git](https://git-scm.com/downloads)

## Quick Install (Recommended)

### macOS / Linux

Open your terminal and run:

```bash
git clone https://github.com/MRI-Lab-Graz/prism-validator.git
cd prism-validator
bash scripts/setup/setup.sh
```

### Windows

Open Command Prompt or PowerShell and run:

```cmd
git clone https://github.com/MRI-Lab-Graz/prism-validator.git
cd prism-validator
scripts\setup\setup-windows.bat
```

This will:
1.  Create a Python virtual environment (`.venv`).
2.  Install all necessary dependencies.
3.  Prepare the application for use.

## Manual Installation

If you prefer to set it up manually:

```bash
# 1. Clone the repository
git clone https://github.com/MRI-Lab-Graz/prism-validator.git
cd prism-validator

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate the environment
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt
```

## Verifying Installation

To check if everything is installed correctly, try running the help command:

```bash
# macOS/Linux
source .venv/bin/activate
python prism-validator.py --help

# Windows
.venv\Scripts\activate
python prism-validator.py --help
```

If you see the help message, you are ready to go!
