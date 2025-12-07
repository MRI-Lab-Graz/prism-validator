# Prism-Validator: BIDS Extension & Validation Tool

[![Documentation Status](https://readthedocs.org/projects/prism-validator/badge/?version=latest)](https://prism-validator.readthedocs.io/en/latest/?badge=latest)

## 🚀 Quick Start

**👉 Run the web interface** (recommended for all users):

```bash
bash scripts/setup/setup.sh    # One-time setup (macOS/Linux)
python prism-validator-web.py
```

The web interface will open automatically at `http://localhost:5001`. No additional configuration needed!

---

## Overview

Prism-Validator is a **BIDS Extension** framework and validation tool designed to enrich standard BIDS datasets with psychological and physiological metadata.

**Core Philosophy: Extension, not Replacement**
- **BIDS Core**: The main architecture remains standard BIDS. Files like `participants.tsv`, `dataset_description.json`, and standard modalities (`anat`, `func`, `eeg`) are preserved and validated according to BIDS standards.
- **PRISM Extensions**: We add structured support for modalities not yet fully standardized in BIDS, specifically **Survey** and **Biometrics**.

## ✨ Key Features

### 🧬 BIDS Extensions
- **Survey Modality (`survey/`)**: Full support for complex questionnaires (LimeSurvey integration), treating surveys as rich data with sidecar metadata.
- **Biometrics Modality (`biometrics/`)**: Structured storage for physiological assessments (VO2max, planks, balance tests) that don't fit into standard `beh` or `physio` categories.
- **Non-Destructive**: Your standard BIDS files (`participants.tsv`, `dataset_description.json`) remain untouched. We only validate the extensions.

### 🎯 Web Interface (Primary Method)
- **Drag & drop dataset upload** - Just drop a folder or ZIP file
- **Interactive validation** - Real-time results with visual charts
- **🧠 NeuroBagel Integration** - Annotate participants with standardized ontologies
  - Professional annotation widget for participant metadata
  - Integration with official NeuroBagel dictionary
  - SNOMED-CT shorthand URI support
  - Auto-detect and parse participants.tsv files
  - Categorical value extraction and labeling
- **JSON Editor** - Edit and create metadata files interactively
- **Local processing** - All data stays on your machine (no cloud uploads)
- **Cross-platform** - Works on Windows, macOS, and Linux
- **Responsive design** - Works on desktop and mobile browsers

## 🛠️ Survey Data Import Workflow
A complete toolset for converting external survey data (CSV/Excel) into PRISM-compliant datasets:
1.  **Excel to Library**: Convert data dictionaries into a "Golden Master" JSON library (via `prism_tools.py survey import-excel`).
2.  **Library Validation**: Ensure variable uniqueness and generate catalogs (via `prism_tools.py survey validate`).

## 🔌 Prism Tools (CLI)

For advanced data conversion tasks, use the `prism_tools.py` utility.

### Physiological Data Conversion

```bash
./prism_tools.py convert physio \
  --input ./sourcedata \
  --output ./rawdata \
  --task rest \
  --suffix ecg \
  --sampling-rate 256
```

### Survey & Demo Tools

```bash
# Create a demo dataset
./prism_tools.py demo create --output my_demo

# Import survey library from Excel
./prism_tools.py survey import-excel --excel metadata.xlsx

# Validate survey library
./prism_tools.py survey validate

# Import LimeSurvey structure
./prism_tools.py survey import-limesurvey --input survey.lsa
```

See [`docs/PRISM_TOOLS.rst`](docs/PRISM_TOOLS.rst) for full documentation.

### 1. Prepare your `sourcedata`
Before conversion, organize your raw files into a BIDS-compliant `sourcedata` structure. This ensures the tool can automatically detect subjects and sessions.

```text
sourcedata/
  sub-1292001/
    ses-1/
      physio/
        sub-1292001_ses-1_physio.raw   <-- Renamed from VPDATA.RAW
  sub-1292002/
    ses-1/
      physio/
        sub-1292002_ses-1_physio.raw
```

### 2. Run the Conversion
Use the `convert physio` command to process the data.

```bash
./prism_tools.py convert physio \
  --input ./sourcedata \
  --output ./rawdata \
  --task rest \
  --suffix ecg \
  --sampling-rate 256
```

**Arguments:**
*   `--input`: Path to your organized `sourcedata` folder.
*   `--output`: Where the BIDS-compliant `rawdata` should be generated.
*   `--task`: The task name to assign (e.g., `rest`, `task`).
*   `--suffix`: The filename suffix (e.g., `ecg`, `physio`).
*   `--sampling-rate`: (Optional) Force a specific sampling rate if the header is incorrect.
3.  **Data Import**: Automatically extract data from raw CSVs and generate BIDS file structures (`scripts/csv_to_prism.py`).

[Read the full guide here](docs/SURVEY_DATA_IMPORT.md).

### ✅ Validation Features
- **Multi-modal validation**: Supports survey, biometrics, and physiological data
- **BIDS-App Compatibility**: Automatically updates `.bidsignore` to ensure custom modalities are ignored by standard BIDS tools (e.g., fMRIPrep), preventing crashes.
- **BIDS-inspired naming**: Validates filenames follow the pattern `sub-<label>_[ses-<label>_]task-<label>_[run-<index>_]<suffix>`
- **JSON schema validation**: Validates sidecar metadata against modality-specific schemas
- **Schema versioning**: Multiple schema versions (stable, v0.1, etc.) selectable in UI
- **Flexible structure**: Supports both session-based and direct subject organization
- **Cross-subject consistency**: Warns when subjects have inconsistent modalities or tasks
- **Comprehensive reporting**: 
  - Dataset summary with subject/session counts
  - Modality breakdown with file counts
  - Task detection and listing
  - **Survey & Biometrics listing**: Lists found instruments with their full names (e.g., `ads - Allgemeine Depressions Skala`)
  - File statistics (data files vs sidecars)
  - Cross-subject consistency warnings
  - Clear error and warning categorization

## Directory Structure

```
dataset/
├── dataset_description.json     # Standard BIDS metadata
├── participants.tsv            # Standard BIDS participant info
├── sub-<label>/               # Subject directories
│   ├── ses-<label>/          # Optional session directories
│   │   ├── survey/           # 📋 Extension: Questionnaires
│   │   ├── biometrics/       # 💓 Extension: Physio assessments
│   │   └── <modality>/       # Standard BIDS (anat, func, etc.)
│   └── <modality>/           # Or direct modality folders
```

## Supported Modalities

| Modality | File Extensions | Required Fields |
|----------|----------------|-----------------|
| `survey` | .tsv | StimulusType, FileFormat, TaskName, OriginalName |
| `biometrics` | .tsv | StimulusType, FileFormat, Equipment, BiometricName, OriginalName |
| `events` | .tsv | StimulusPresentation (OperatingSystem, SoftwareName) |
| `physiological` | .edf, .bdf, .txt, .csv | (Standard BIDS physio) |

## Super-BIDS: Enhanced Validation

Prism-Validator implements a "Super-BIDS" layer—a stricter set of validation rules that sits on top of standard BIDS to ensure higher data quality and reproducibility.

### Why "Super-BIDS"?
Standard BIDS is excellent for file organization but often permissive with metadata. "Super-BIDS" enforces mandatory fields that are critical for scientific reproducibility but optional in the base standard.

### Enhanced Modalities

#### 1. Biometrics (`biometrics/`)
We enforce a rich set of metadata for physiological assessments to ensure the protocol is fully documented.
- **Mandatory Fields**: `Description` (detailed protocol).
- **Recommended Fields**: `Instructions`, `Author`, `DOI`, `Reference`, `EstimatedDuration`, `TargetPopulation`, `ExclusionCriteria`.

#### 2. Events (`*_events.tsv`)
Standard BIDS allows minimal event files. We enforce the `StimulusPresentation` object to ensure we know exactly how stimuli were delivered.
- **Mandatory Object**: `StimulusPresentation`
- **Required Fields**: 
  - `OperatingSystem`
  - `SoftwareName`
  - `SoftwareRRID` (Recommended)
  - `SoftwareVersion` (Recommended)

This ensures that years later, you know exactly what software version and OS were used to run the experiment.

## Schema Structure

Each stimulus file must have a corresponding `.json` sidecar file with the same basename. These JSON files contain metadata about the stimulus and are validated against JSON schemas in the `schemas/` directory.

### Example Survey Metadata (`.json` sidecar):
```json
{
  "StimulusType": "Survey",
  "FileFormat": "tsv",
  "TaskName": "bdi",
  "OriginalName": "Beck Depression Inventory",
  "SchemaVersion": "1.0.0"
}
```

### Example Biometrics Metadata (`.json` sidecar):
```json
{
  "Technical": {
    "StimulusType": "Biometrics",
    "FileFormat": "tsv",
    "Equipment": "Stopwatch"
  },
  "Study": {
    "BiometricName": "UKK",
    "OriginalName": "UKK Walk Test",
    "Protocol": "2k walk"
  },
  "Metadata": {
    "SchemaVersion": "1.0.0",
    "CreationDate": "2023-01-01"
  }
}
```

## Usage

### Basic validation:
```bash
python prism-validator.py /path/to/dataset
```

### Verbose output (shows scanning details):
```bash
python prism-validator.py /path/to/dataset -v
```

### Example Output:

For a valid dataset:
```
🔍 Validating dataset: valid_test_dataset/

============================================================
🗂️  DATASET SUMMARY
============================================================
📁 Dataset: valid_test_dataset
👥 Subjects: 2
📋 Sessions: No session structure detected

🎯 MODALITIES (2 found):
  ✅ survey: 2 files
  ✅ biometrics: 2 files

📝 TASKS (0 found):
  No tasks detected

📋 SURVEYS (1 found):
  • bdi - Beck Depression Inventory

🧬 BIOMETRICS (1 found):
  • ukk - UKK Walk Test

📄 FILES:
  • Data files: 4
  • Sidecar files: 4
  • Total files: 8

============================================================
✅ VALIDATION RESULTS
============================================================
🎉 No issues found! Dataset is valid.
```

For a dataset with issues:
```
============================================================
🔍 VALIDATION RESULTS
============================================================

🔴 ERRORS (1):
   1. Missing sidecar for test_dataset/sub-003/image/invalid-file.jpg

� WARNINGS (3):
   1. Subject sub-003 session ses-001 missing audio data
   2. Subject sub-003 session ses-001 missing task soundrecognition
   3. Mixed session structure: 2 subjects have sessions, 1 don't

�📊 SUMMARY: 1 errors, 3 warnings
❌ Dataset validation failed due to errors.
```

## Consistency Checking

The validator performs cross-subject consistency checks to ensure scientific rigor:

- **Modality consistency**: All subjects should have the same modalities (e.g., if one subject has both image and audio data, all should)
- **Task consistency**: All subjects should perform the same tasks within each session
- **Session structure**: Warns if mixing subjects with and without session directories
- **Per-session consistency**: For multi-session studies, ensures each subject has consistent data across sessions

These checks generate **warnings** (not errors) since missing data might be due to technical issues, dropouts, or valid experimental design decisions.

### Exit codes:
- `0`: Dataset is valid
- `1`: Validation errors found

## Test Dataset

The included `test_dataset/` demonstrates:
- ✅ Valid files with proper naming and metadata
- ❌ Invalid naming conventions
- ❌ Missing sidecar files
- ✅ Mixed session/no-session structures

## 📁 Repository Structure

- **`prism-validator-web.py`** - **✨ MAIN ENTRY POINT** - Web interface with NeuroBagel integration
- `schemas/` - JSON schemas for each modality
- `docs/` - Documentation (web interface guide, examples, NeuroBagel integration)
- `tests/` - Test dataset and test scripts
- `src/` - Core validation and utility modules
- `static/` - Web interface assets (CSS, JavaScript, NeuroBagel widget)
- `templates/` - Web interface templates (HTML)
- `archive/` - Legacy scripts (not tracked in git)

### Additional Files
- `prism-validator.py` - Command-line tool (see footnote below)
- `scripts/setup/setup.sh` / `scripts/setup/setup-windows.bat` - Installation scripts
- `requirements.txt` - Python dependencies

## 🔬 NeuroBagel Integration (v1.1.0+)

The JSON Editor now includes professional **NeuroBagel annotation tools** for standardizing participant metadata:

### Features:
- **Automatic TSV Parsing**: Loads unique values from `participants.tsv`
- **Smart Categorization**: Separates available columns from suggestions
- **Data Type Detection**: Auto-detects continuous vs. categorical variables
- **Ontology Integration**: Add SNOMED-CT URIs to categorical levels
- **Standardized Export**: Downloads annotated `participants.json` with full BIDS compliance

### Workflow:
1. Upload dataset with `participants.json` and `participants.tsv`
2. Go to JSON Editor → Select "Annotate Participants"
3. Edit column descriptions, units, and categorical levels
4. Add ontology URIs (SNOMED-CT shorthand: `snomed:248153007`)
5. Download annotated file to replace original

See [`docs/NEUROBAGEL_INTEGRATION_STRATEGY.md`](docs/NEUROBAGEL_INTEGRATION_STRATEGY.md) for details.

---

## 📊 LimeSurvey Integration

Prism-Validator now includes a complete workflow for integrating LimeSurvey questionnaires into the BIDS/PRISM structure.

### Features:
- **Automated Conversion**:
  - `LimeSurvey (.lss) -> PRISM JSON`: Create sidecars from survey structures
  - `PRISM JSON -> LimeSurvey (.lss)`: Generate importable surveys from sidecars
- **Data Merging**: Combine multiple questionnaire templates into a single BIDS sidecar
- **Dataset-level sidecars**: Validator now resolves shared `survey-<name>_beh.json` files at the dataset root, so you only keep one canonical JSON per instrument.
- **Redaction tooling**: `helpers/utils/redact_sidecar.py` can strip or hash copyrighted prompts before publishing.

### Workflow:
1. **Create/Export**: Design survey in LimeSurvey (using standard naming `BDI_01`, `ADS_01`) and export structure (`.lss`).
2. **Convert**: Run `helpers/surveys/limesurvey_to_prism.py` to generate the JSON sidecar.
3. **Collect**: Run study, export data to TSV.
4. **Combine**: Use `helpers/surveys/combine_survey_json.py` to merge multiple sidecars for the final dataset.

## 📚 Survey Library (New)

A robust management system for questionnaire templates ("Golden Masters") with a **Draft & Publish** workflow.

### Key Features:
- **Read-Only Masters**: Prevents accidental overwrites of production files.
- **Draft Mode**: Checkout files to `drafts/` for safe editing.
- **Automated Validation**: Submissions are checked for variable name conflicts across the entire library.
- **Merge Requests**: Validated drafts are submitted to `merge_requests/` for final review.
- **GUI Editor**: User-friendly web interface for editing questions, ranges, and metadata.

See [`docs/SURVEY_LIBRARY.md`](docs/SURVEY_LIBRARY.md) for the full guide.

---

## 📊 LimeSurvey Integration
5. **Redact (optional)**: Run `helpers/utils/redact_sidecar.py` to produce a public-safe copy of the sidecar if the instrument text is licensed.

See [`docs/LIMESURVEY_INTEGRATION.md`](docs/LIMESURVEY_INTEGRATION.md) for the full guide.

---

## 📚 Additional Resources

- **[Web Interface Documentation](docs/WEB_INTERFACE.md)** - Detailed UI guide
- **[NeuroBagel Integration](docs/NEUROBAGEL_INTEGRATION_STRATEGY.md)** - Annotation tool usage
- **[Schema Versioning Guide](docs/SCHEMA_VERSIONING_GUIDE.md)** - Multiple schema versions
- **[Examples](docs/examples/)** - Test datasets and example files
- **[FAIR Implementation](docs/FAIR_IMPLEMENTATION.md)** - FAIR data principles

---

## 🔮 Future Enhancements

1. **Additional modalities**: Add schemas for eye-tracking
2. **Cross-file validation**: Validate stimulus-response timing relationships
3. **BIDS compatibility**: Ensure full compatibility with official BIDS standard
4. **Batch processing**: Support for validating multiple datasets via web UI
5. **Export formats**: BIDS package export, DataLad integration

## Installation

### ⚡ Quick Setup (Recommended)

**macOS/Linux:**
```bash
git clone https://github.com/MRI-Lab-Graz/prism-validator.git
cd prism-validator
bash scripts/setup/setup.sh
python prism-validator-web.py
```

**Windows:**
```cmd
git clone https://github.com/MRI-Lab-Graz/prism-validator.git
cd prism-validator
scripts\setup\setup-windows.bat
python prism-validator-web.py
```

The web interface opens automatically! 🌐

### Manual Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run web interface
python prism-validator-web.py
```

---

## 📖 Usage Guide

### 🌐 Web Interface (Primary - Recommended for All Users)

Simply run:
```bash
python prism-validator-web.py
```

The interface opens at `http://localhost:5001` with three main sections:

#### 1. **Dataset Validation** (Home Tab)
- Drag & drop your dataset folder or ZIP file
- Select schema version (stable/v0.1)
- Get instant validation results with visual charts

#### 2. **JSON Editor** (JSON Editor Tab)
- Edit dataset_description.json and other metadata
- Create new metadata files
- **NeuroBagel Annotation Tool** (if participants.json exists):
  - Load your dataset with participants.json
  - Select "Annotate Participants" 
  - Annotation widget loads your participants.tsv data
  - Edit descriptions, units, and categorical levels
  - Add SNOMED-CT URIs for ontology standardization
  - Download annotated participants.json

#### 3. **Home Page**
- Introduction and quick links
- Feature overview
- Getting started guide

**Features:**
- ✅ All processing happens locally (no data leaves your machine)
- ✅ Real-time validation feedback
- ✅ Support for folder and ZIP uploads
- ✅ Interactive metadata editing
- ✅ Professional annotation with NeuroBagel

See [`docs/WEB_INTERFACE.md`](docs/WEB_INTERFACE.md) for detailed instructions.

---

### 📝 Command-Line Interface (Advanced/Automation)

For automation and scripting, use the CLI:

```bash
# Activate virtual environment first
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows

# Basic validation (uses stable schema)
python prism-validator.py /path/to/dataset

# Validate with specific schema version
python prism-validator.py /path/to/dataset --schema-version v0.1

# List available schema versions
python prism-validator.py --list-versions

# Verbose output
python prism-validator.py /path/to/dataset -v

# Show help
python prism-validator.py --help
```

**Note:** This is primarily for automation and batch processing. The web interface is recommended for interactive use.

#### Schema Versions

Available schema versions:
- **`stable`** (default) - Current recommended version
- **`v0.1`** - Version 0.1

See [`docs/SCHEMA_VERSIONING_GUIDE.md`](docs/SCHEMA_VERSIONING_GUIDE.md) for details.

## Dependencies

- Python 3.6+
- `jsonschema` - For JSON schema validation
- `flask` - Web interface framework
- `requests` - HTTP client for NeuroBagel API

Optional (for dummy file generation):
- `Pillow` - For creating test images
- `numpy` - For generating test data

---

## 📝 Footnote: Command-Line Tool

While the **web interface is the primary and recommended method** for using Prism-Validator, a command-line interface is also available for automation and batch processing.

**Command-line tool usage:**
```bash
python prism-validator.py /path/to/dataset [--schema-version VERSION] [-v]
```

This is useful for:
- CI/CD pipelines and automated testing
- Batch processing multiple datasets
- Scripting and automation workflows
- Integration with other tools

For most users and interactive validation, please use the web interface instead.

---

## 💡 License & Attribution

See LICENSE file for details.

For questions or contributions, visit the [GitHub repository](https://github.com/MRI-Lab-Graz/prism-validator).
