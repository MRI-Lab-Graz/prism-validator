# Usage Guide

Prism-Validator offers two ways to validate your data: a user-friendly **Web Interface** and a powerful **Command Line Interface (CLI)**.

## 🖥️ Web Interface (Recommended)

The web interface is the easiest way to validate your data. It provides a visual dashboard, drag-and-drop support, and detailed error reports.

### Starting the Web Interface

1.  **Open your terminal/command prompt.**
2.  **Navigate to the prism-validator folder.**
3.  **Run the start command:**

    **macOS / Linux:**
    ```bash
    source .venv/bin/activate
    python prism-validator-web.py
    ```

    **Windows:**
    ```bat
    .venv\Scripts\activate
    python prism-validator-web.py
    ```

4.  **Open your browser** and go to `http://127.0.0.1:5001`.

### Validating Data

1.  **Select Schema Version**: Choose between `stable` (recommended) or specific versions like `v0.1`.
2.  **Upload Data**:
    *   **Drag & Drop**: Drag your dataset folder directly onto the drop zone.
    *   **Select Folder**: Click to browse for a local folder.
    *   **Upload ZIP**: Upload a compressed `.zip` file of your dataset.
3.  **View Results**:
    *   The dashboard will show a summary of **Errors** (must fix) and **Warnings** (should fix).
    *   Click on any error to see exactly which file is affected and how to fix it.
4.  **Download Report**: You can download a full JSON report of the validation results.

Notes
-----

- **Structure-only uploads**: For large datasets, the Web UI may upload only metadata (e.g., `.json`, `.tsv`) and create placeholders for large binaries. In this mode, the validator checks dataset structure, filenames, and sidecar/schema consistency without transferring large imaging/stimulus files.
- **Dataset description**: `dataset_description.json` is required and validated against the selected schema version.
- **BIDS compatibility**: When validating, the tool may update `.bidsignore` to hide PRISM-only folders from standard BIDS tools/apps.

---

## ⌨️ Command Line Interface (CLI)

For advanced users or batch processing, the CLI allows you to run validations directly from the terminal.

### Basic Usage

```bash
python prism-validator.py /path/to/your/dataset
```

### Options

| Flag | Description | Example |
|------|-------------|---------|
| `--schema-version` | Specify which schema version to use (default: `stable`). | `python prism-validator.py /data --schema-version v0.1` |
| `-v`, `--verbose` | Show detailed progress and file scanning info. | `python prism-validator.py /data -v` |
| `--bids` | Run the standard BIDS validator in addition to PRISM validation. | `python prism-validator.py /data --bids` |
| `--bids-warnings` | Show warnings from the BIDS validator (default: hidden). | `python prism-validator.py /data --bids --bids-warnings` |
| `--list-versions` | Show all available schema versions. | `python prism-validator.py --list-versions` |

### Example Output

```text
🔍 Validating dataset: /data/study-01

============================================================
🗂️  DATASET SUMMARY
============================================================
👥 Subjects: 15
🎯 MODALITIES:
  ✅ survey: 15 files
  ✅ biometrics: 15 files

============================================================
✅ VALIDATION RESULTS
============================================================
🎉 No issues found! Dataset is valid.
```
