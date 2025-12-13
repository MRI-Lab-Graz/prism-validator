# Prism-Validator AI Instructions

## Project Overview
Prism-Validator is a hybrid dataset validation tool for psychological experiments. It enforces a "PRISM" structure (BIDS-inspired, with additional metadata requirements) while remaining compatible with standard BIDS tools/apps. It consists of a core Python validation library and a Flask-based web interface.

## Architecture & Components
- **Core Logic (`src/`)**:
  - `validator.py`: Contains `DatasetValidator` class. Handles filename patterns and JSON schema validation.
  - `schema_manager.py`: Loads schemas from `schemas/` directory based on version (e.g., `stable`, `v0.1`).
  - `runner.py`: Main entry point `validate_dataset()` used by both CLI and Web UI.
  - `bids_integration.py`: Manages `.bidsignore` to ensure compatibility with BIDS apps (fMRIPrep).
- **Web Interface**:
  - `prism-validator-web.py`: Flask application. Handles uploads, session management, and invokes `runner.py`.
  - `templates/`: Jinja2 HTML templates. `index.html` is the SPA-like main page.
- **Schemas (`schemas/`)**:
  - JSON Schema definitions for modalities: `image`, `movie`, `audio`, `eyetracking`, `survey`, `physiological`.
  - **Versioning**: Schemas are organized by version folders (`stable/`, `v0.1/`).

## Validation Logic & Data Model
1.  **PRISM vs. BIDS**:
    - **PRISM**: Uses nested JSON keys (e.g., `Technical.SamplingRate`). Enforced by schemas in `schemas/`.
    - **BIDS**: Uses flat JSON keys (e.g., `SamplingFrequency`).
  - **BIDS validator (optional)**: The tool can run the standard BIDS validator in addition to PRISM validation.
2.  **Modalities**:
    - `survey` (formerly `behavior`): `.tsv` files.
    - `eeg`: No specific PRISM schema (relies on BIDS standard).
    - `image`, `movie`, `audio`: Custom PRISM schemas.
3.  **Validation Steps**:
    - **Filename**: Must match `sub-<id>_[ses-<id>_]task-<id>_<suffix>.<ext>`.
    - **Sidecar**: Every data file (except `.json`) MUST have a corresponding `.json` sidecar.
    - **Schema**: Sidecar content is validated against the loaded JSON schema.

## Web Interface Patterns
- **Upload Strategy**:
  - **"DataLad-style"**: For large datasets, the frontend filters files. Only metadata (`.json`, `.tsv`) is uploaded. Large data files (`.nii`, `.mp4`) are skipped, and the backend creates empty placeholders to validate structure without transfer overhead.
  - **Batch Optimization**: File paths are sent as a JSON string (`metadata_paths_json`) to handle 5000+ files without hitting form field limits.
- **NeuroBagel Integration**:
  - `src/json_editor/`: Blueprint for editing `participants.json`.
  - Uses `participants.tsv` to auto-populate categorical levels.

## Developer Workflows
- **Running Web UI**: `python prism-validator-web.py` (runs on port 5001).
- **CLI Usage**: `python prism-validator.py /path/to/dataset`.
- **Schema Updates**:
  - When renaming/adding modalities, update:
    1. `schemas/` filenames.
    2. `src/schema_manager.py` (`modalities` list).
    3. `src/validator.py` (`MODALITY_PATTERNS`).
    4. `prism-validator-web.py` (`restricted_names`).
    5. `templates/index.html` (UI list).

## Key Conventions
- **Cross-Platform**: Always use `src.cross_platform` utilities for path handling.
- **System Files**: Always filter `.DS_Store`, `Thumbs.db` using `system_files.filter_system_files`.

