#!/usr/bin/env python3
"""
Web interface for prism-validator
A simple Flask web app that provides a user-friendly interface for dataset validation
"""

import os
import sys
import json
import tempfile
import shutil
import webbrowser
import threading
from pathlib import Path
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    flash,
    redirect,
    url_for,
)
from werkzeug.utils import secure_filename
import zipfile
import io
import requests
from functools import lru_cache

# Ensure we can import core validator logic from src
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    BASE_DIR = Path(sys._MEIPASS)
else:
    # Running in a normal Python environment
    BASE_DIR = Path(__file__).resolve().parent

SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from runner import validate_dataset as core_validate_dataset
except Exception as import_error:
    core_validate_dataset = None
    print(f"⚠️  Could not import core validator: {import_error}")

try:
    from limesurvey_exporter import generate_lss
except Exception as import_error:
    generate_lss = None
    print(f"⚠️  Could not import limesurvey_exporter: {import_error}")

try:
    from survey_manager import SurveyManager
except Exception as import_error:
    SurveyManager = None
    print(f"⚠️  Could not import SurveyManager: {import_error}")


class SimpleStats:
    """Simple stats class to hold validation statistics"""

    def __init__(self, *args):
        self.total_files = 0
        self.subjects = set()
        self.sessions = set()
        self.tasks = set()
        self.modalities = set()


# Use subprocess to run the main validator script - single source of truth
def run_main_validator(dataset_path, verbose=False, schema_version=None, run_bids=False):
    """
    Run the validation logic.
    Prefer importing core logic directly. Fallback to subprocess if needed.
    """
    # Try to use core validator directly first
    if core_validate_dataset:
        try:
            issues, stats = core_validate_dataset(
                dataset_path, 
                verbose=verbose, 
                schema_version=schema_version,
                run_bids=run_bids
            )
            
            # Convert issues to web format if needed
            # core_validate_dataset returns list of tuples. 
            # If they are (level, msg), we need to add path.
            # If they are (level, msg, path), we are good.
            
            web_issues = []
            for issue in issues:
                if len(issue) == 2:
                    web_issues.append((issue[0], issue[1], dataset_path))
                else:
                    web_issues.append(issue)
            
            return web_issues, stats
        except Exception as e:
            print(f"⚠️  Error running core validator directly: {e}")
            # Fallthrough to subprocess if direct call fails (though unlikely to work in frozen app)

    import subprocess
    import re

    try:
        # Run the main validator script
        cmd = [sys.executable, "prism-validator.py", dataset_path]
        if verbose:
            cmd.append("--verbose")
        if schema_version:
            cmd.extend(["--schema-version", schema_version])
        if run_bids:
            cmd.append("--bids")

        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=os.path.dirname(__file__)
        )

        # Helper to strip ANSI codes
        def strip_ansi(text):
            ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
            return ansi_escape.sub("", text)

        # The validator script exits with 0 for success, 1 for validation errors.
        # We need to parse the output in both cases.
        if result.returncode in [0, 1]:
            # Parse the terminal output to extract validation results
            stdout = result.stdout
            stderr = result.stderr

            # Extract statistics from output
            stats = SimpleStats()
            issues = []

            # Parse output for file counts and issues
            for line in stdout.split("\n") + stderr.split("\n"):
                clean_line = strip_ansi(line).strip()

                # Parse file count from the new output format
                if "Total files:" in clean_line:
                    match = re.search(r"Total files:\s*(\d+)", clean_line)
                    if match:
                        stats.total_files = int(match.group(1))
                elif "📊 Found" in clean_line and "files" in clean_line:
                    match = re.search(r"Found (\d+) files", clean_line)
                    if match:
                        stats.total_files = int(match.group(1))
                # Parse error and warning counts
                elif "Errors:" in clean_line:
                    match = re.search(r"Errors:\s*(\d+)", clean_line)
                    if match and int(match.group(1)) > 0:
                        # Add a generic error - we'll get the specific errors from other lines
                        pass
                elif "Warnings:" in clean_line:
                    match = re.search(r"Warnings:\s*(\d+)", clean_line)
                    if match and int(match.group(1)) > 0:
                        # Add a generic warning - we'll get the specific warnings from other lines
                        pass
                # Parse specific error messages (bullet style)
                elif clean_line.startswith("•") and (
                    "❌" in stdout or "ERROR" in stdout
                ):
                    # This is a specific error message
                    issues.append(
                        ("ERROR", clean_line.replace("•", "").strip(), dataset_path)
                    )
                # Parse numbered error messages (reporting.py style)
                elif re.search(r"^\d+\.\s+", clean_line) and (
                    "❌" in stdout or "ERROR" in stdout
                ):
                    # Remove the number and dot
                    msg = re.sub(r"^\d+\.\s+", "", clean_line).strip()
                    issues.append(("ERROR", msg, dataset_path))

                elif clean_line.startswith("•") and (
                    "⚠️" in stdout or "WARNING" in stdout
                ):
                    # This is a specific warning message
                    issues.append(
                        ("WARNING", clean_line.replace("•", "").strip(), dataset_path)
                    )
                # Parse numbered warning messages
                elif re.search(r"^\d+\.\s+", clean_line) and (
                    "⚠️" in stdout or "WARNING" in stdout
                ):
                    msg = re.sub(r"^\d+\.\s+", "", clean_line).strip()
                    issues.append(("WARNING", msg, dataset_path))

            # If we got valid output, extract more detailed info
            if "✅ Dataset is valid!" in stdout:
                pass  # No issues to add
            elif "❌ Dataset has validation errors" in stdout:
                if not issues:  # Add generic error if no specific issues found
                    issues.append(
                        (
                            "ERROR",
                            "Dataset validation failed - see terminal output for details",
                            dataset_path,
                        )
                    )
            elif result.returncode != 0 and not issues:
                # Add error for non-zero exit code if we didn't parse any specific errors
                issues.append(("ERROR", "Dataset validation failed", dataset_path))

            return issues, stats

        else:
            # Handle validation failures
            error_msg = result.stderr or "Validation failed"
            print(
                f"❌ Validator subprocess failed (code {result.returncode}): {error_msg}"
            )

            # Create minimal stats and error
            stats = SimpleStats()
            issues = [
                ("ERROR", f"Validation process failed: {error_msg}", dataset_path)
            ]
            return issues, stats

    except FileNotFoundError:
        error_msg = "prism-validator.py script not found"
        print(f"❌ {error_msg}")
        stats = SimpleStats()
        issues = [("ERROR", error_msg, dataset_path)]
        return issues, stats

    except Exception as e:
        error_msg = f"Failed to run validator: {str(e)}"
        print(f"❌ {error_msg}")
        stats = SimpleStats()
        issues = [("ERROR", error_msg, dataset_path)]
        return issues, stats




    def check_consistency(self):
        return []


def simple_is_system_file(filename):
    """Simple system file detection"""
    if not filename:
        return True
    system_files = [
        ".DS_Store",
        "._.DS_Store",
        "Thumbs.db",
        "ehthumbs.db",
        "Desktop.ini",
    ]
    if filename in system_files:
        return True
    if filename.startswith("._") or filename.startswith(".#"):
        return True
    return False


# Use simple system file detection
is_system_file = simple_is_system_file

if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

app.secret_key = "prism-validator-secret-key"  # Change this in production
app.config["MAX_CONTENT_LENGTH"] = (
    1024 * 1024 * 1024
)  # 1GB max file size (metadata only)
app.config["MAX_FORM_PARTS"] = 20000  # Allow up to 20000 files/fields in upload

# Initialize Survey Manager
survey_library_path = BASE_DIR / "survey_library"
survey_manager = None
if SurveyManager:
    survey_manager = SurveyManager(survey_library_path)
    print(f"✓ Survey Manager initialized at {survey_library_path}")

# Register JSON Editor blueprint if available
try:
    from src.json_editor_blueprint import create_json_editor_blueprint

    json_editor_bp = create_json_editor_blueprint(bids_folder=None)
    app.register_blueprint(json_editor_bp)
    print("✓ JSON Editor blueprint registered at /editor")
except ImportError as e:
    print(f"ℹ️  JSON Editor not available: {e}")
except Exception as e:
    print(f"⚠️  Error registering JSON Editor blueprint: {e}")

# File extensions to process (metadata and small data files only)
# We skip large neuroimaging data files - we only validate their JSON sidecars
METADATA_EXTENSIONS = {
    ".json",  # Sidecar metadata
    ".tsv",  # Behavioral/events data
    ".csv",  # Alternative tabular format
    ".txt",  # Text data/logs
    ".edf",  # EEG/eye-tracking (relatively small)
    ".bdf",  # BioSemi EEG format
    ".png",
    ".jpg",
    ".jpeg",  # Stimulus images (psychology experiments)
}

# Extensions to SKIP (large data files we don't need)
SKIP_EXTENSIONS = {
    ".nii",
    ".nii.gz",  # NIfTI neuroimaging (can be GB)
    ".mp4",
    ".avi",
    ".mov",  # Video files
    ".tiff",  # Large TIFF images
    ".eeg",
    ".dat",
    ".fif",  # Large electrophysiology raw data
    ".mat",  # MATLAB files (can be large)
}


def format_validation_results(issues, dataset_stats, dataset_path):
    """Format validation results in BIDS-validator style with grouped errors"""
    # Group issues by error code and type
    error_groups = {}
    warning_groups = {}

    valid_files = []
    invalid_files = []
    file_paths = set()

    def strip_temp_path(file_path):
        """Strip temporary folder path prefix and keep only relative path from dataset root"""
        if not file_path:
            return None

        # If it's a temp path, try to extract the relative path
        if (
            "/tmp/" in file_path
            or "/T/prism_validator_" in file_path
            or "/var/folders/" in file_path
            or "prism_validator_" in file_path
        ):
            # Find the dataset root marker - typically after 'dataset/'
            if "/dataset/" in file_path:
                parts = file_path.split("/dataset/", 1)
                if len(parts) > 1:
                    return parts[1]

            # Alternative: look for BIDS structure markers (sub-, dataset_description.json)
            import re

            match = re.search(r"((?:sub-|ses-|dataset_description\.json).*)", file_path)
            if match:
                return match.group(1)

        # If dataset_path is a temp directory, strip it
        if dataset_path and file_path.startswith(dataset_path):
            relative = file_path[len(dataset_path) :].lstrip("/")
            return relative if relative else file_path

        return file_path

    def extract_path_from_message(msg):
        """Try to heuristically extract a file path or filename from a validator message."""
        if not msg:
            return None
        # If message explicitly contains an absolute path
        import re

        abs_path_match = re.search(r"(/[^\s:,]+\.[A-Za-z0-9]+(?:\.gz)?)", msg)
        if abs_path_match:
            extracted = abs_path_match.group(1)
            return strip_temp_path(extracted)
        # dataset_description.json special case
        if "dataset_description.json" in msg:
            return "dataset_description.json"
        # Look for sub-... filenames like sub-01_task-foo_blah.ext
        name_match = re.search(r"(sub-[A-Za-z0-9._-]+\.[A-Za-z0-9]+(?:\.gz)?)", msg)
        if name_match:
            return name_match.group(1)
        # Generic filename with extension (e.g., task-recognition_stim.json)
        generic_match = re.search(
            r"([A-Za-z0-9._\-]+\.(?:json|tsv|edf|nii|nii\.gz|txt|csv|mp4|png|jpg|jpeg))",
            msg,
        )
        if generic_match:
            return generic_match.group(1)
        return None

    for issue in issues:
        # Support tuples like (level, message) or (level, message, path)
        if isinstance(issue, dict):
            level = (
                issue.get("type")
                or issue.get("level")
                or issue.get("severity")
                or "ERROR"
            )
            message = issue.get("message", "")
            file_path = issue.get("file")
        elif isinstance(issue, (list, tuple)):
            if len(issue) >= 2:
                level, message = issue[0], issue[1]
                file_path = issue[2] if len(issue) > 2 else None
            else:
                continue
        else:
            # Unknown shape: stringify
            level = "ERROR"
            message = str(issue)
            file_path = None

        # Always strip temp path from file_path
        if not file_path:
            file_path = extract_path_from_message(message)
        file_path = strip_temp_path(file_path) if file_path else None

        if file_path:
            file_paths.add(file_path)

        # Also strip temp path from message text itself
        def strip_temp_path_from_message(msg):
            if not msg:
                return msg
            import re

            # Replace temp folder paths in the message with just the relative path
            # Match various temp folder patterns: /tmp/, /T/, /var/folders/, prism_validator_
            msg = re.sub(
                r"(/tmp/[^\s,:]+/dataset/|/T/prism_validator_[^\s,:]+/dataset/|/var/folders/[^\s,:]+/dataset/|prism_validator_[^\s,:]+/dataset/)([^\s,:]+)",
                r"\2",
                msg,
            )
            # Also replace standalone temp paths that lead to sub- or ses- files
            msg = re.sub(
                r"(/tmp/[^\s,:]+/|/var/folders/[^\s,:]+/)(sub-[^\s,:/]+)", r"\2", msg
            )
            return msg

        message = strip_temp_path_from_message(message)

        # Extract error code from message if possible
        error_code = "GENERAL_ERROR"
        if (
            "Invalid BIDS filename" in message
            or "Invalid BIDS filename format" in message
        ):
            error_code = "INVALID_BIDS_FILENAME"
        elif "Missing sidecar" in message or "Missing sidecar for" in message:
            error_code = "MISSING_SIDECAR"
        elif "schema error" in message:
            error_code = "SCHEMA_VALIDATION_ERROR"
        elif "not valid JSON" in message or "is not valid JSON" in message:
            error_code = "INVALID_JSON"
        elif (
            "doesn't match expected pattern" in message
            or "doesn't match expected pattern" in message
        ):
            error_code = "FILENAME_PATTERN_MISMATCH"

        formatted_issue = {
            "code": error_code,
            "message": message,
            "file": file_path,
            "level": level,
        }

        if level == "ERROR":
            if error_code not in error_groups:
                error_groups[error_code] = {
                    "code": error_code,
                    "description": get_error_description(error_code),
                    "files": [],
                    "count": 0,
                }
            error_groups[error_code]["files"].append(formatted_issue)
            error_groups[error_code]["count"] += 1

            if file_path:
                invalid_files.append({"path": file_path, "errors": [message]})

        elif level == "WARNING":
            if error_code not in warning_groups:
                warning_groups[error_code] = {
                    "code": error_code,
                    "description": get_error_description(error_code),
                    "files": [],
                    "count": 0,
                }
            warning_groups[error_code]["files"].append(formatted_issue)
            warning_groups[error_code]["count"] += 1

            if file_path:
                valid_files.append(
                    {"path": file_path}
                )  # Warnings don't make files invalid
        else:
            # Treat other levels as info/valid
            if file_path:
                valid_files.append({"path": file_path})

    # If we don't have file paths from issues, prefer dataset_stats total
    try:
        stats_total = getattr(dataset_stats, "total_files", 0)
    except Exception:
        stats_total = 0

    # Prefer authoritative dataset_stats.total_files when available so counts align
    if stats_total:
        total_files = stats_total
    else:
        total_files = (
            len(file_paths) if file_paths else len(valid_files) + len(invalid_files)
        )

    # Add error if no files found
    if stats_total == 0 and len(file_paths) == 0:
        # Add a specific error for empty dataset
        error_code = "EMPTY_DATASET"
        if error_code not in error_groups:
            error_groups[error_code] = {
                "code": error_code,
                "description": "Dataset contains no data files",
                "files": [],
                "count": 0,
            }

        empty_dataset_issue = {
            "code": error_code,
            "message": "No data files found in dataset. Dataset may be empty or all files were filtered out as system files.",
            "file": dataset_path,
            "level": "ERROR",
        }
        error_groups[error_code]["files"].append(empty_dataset_issue)
        error_groups[error_code]["count"] += 1

    # Calculate summary
    total_errors = sum(group["count"] for group in error_groups.values())
    total_warnings = sum(group["count"] for group in warning_groups.values())

    # Count valid vs invalid files
    invalid_file_paths = {f["path"] for f in invalid_files if f.get("path")}
    invalid_count = len(invalid_file_paths)
    # If we have dataset total, infer valid_count
    if stats_total:
        valid_count = max(0, stats_total - invalid_count)
    else:
        valid_count = total_files - invalid_count

    # A dataset is valid only if it has no errors AND has at least some files
    is_valid = total_errors == 0 and total_files > 0

    return {
        "valid": is_valid,
        "summary": {
            "total_files": total_files,
            "valid_files": valid_count,
            "invalid_files": invalid_count,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        },
        "error_groups": error_groups,
        "warning_groups": warning_groups,
        "valid_files": valid_files,
        "invalid_files": invalid_files,
        "errors": [item for group in error_groups.values() for item in group["files"]],
        "warnings": [
            item for group in warning_groups.values() for item in group["files"]
        ],
        "dataset_path": dataset_path,
        "dataset_stats": dataset_stats,
    }


def get_error_description(error_code):
    """Get user-friendly descriptions for error codes"""
    descriptions = {
        "INVALID_BIDS_FILENAME": "Filenames must follow BIDS naming convention (sub-<label>_[ses-<label>_]...)",
        "MISSING_SIDECAR": "Required JSON sidecar files are missing for data files",
        "SCHEMA_VALIDATION_ERROR": "JSON sidecar content does not match required schema",
        "INVALID_JSON": "JSON files contain syntax errors or are not valid JSON",
        "FILENAME_PATTERN_MISMATCH": "Filenames do not match expected patterns for their modality",
        "EMPTY_DATASET": "Dataset contains no data files or all files were filtered as system files",
        "GENERAL_ERROR": "General validation error",
    }
    return descriptions.get(error_code, "Validation error")


def get_error_documentation_url(error_code):
    """Get documentation URL for an error code"""
    # Map error codes to documentation anchors
    base_url = (
        "https://github.com/MRI-Lab-Graz/prism-validator/blob/main/docs/ERROR_CODES.md"
    )

    doc_anchors = {
        "INVALID_BIDS_FILENAME": f"{base_url}#invalid_bids_filename",
        "MISSING_SIDECAR": f"{base_url}#missing_sidecar",
        "SCHEMA_VALIDATION_ERROR": f"{base_url}#schema_validation_error",
        "INVALID_JSON": f"{base_url}#invalid_json",
        "FILENAME_PATTERN_MISMATCH": f"{base_url}#filename_pattern_mismatch",
        "GENERAL_ERROR": base_url,
    }
    return doc_anchors.get(error_code, base_url)


@lru_cache(maxsize=8)
def fetch_neurobagel_participants():
    """Fetch NeuroBagel participants dictionary and cache it."""
    url = "https://neurobagel.org/data_models/dictionaries/participants.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def augment_neurobagel_data(raw_data):
    """Augment raw NeuroBagel data with standardized variable mappings and categorical details.

    Transforms flat NeuroBagel data into a hierarchical structure with:
    - Standardized variable mappings (e.g., sex -> biological_sex)
    - Data type classification (categorical vs continuous)
    - Categorical level details with URIs and descriptions
    - Column-level metadata
    """
    if not raw_data or not raw_data.get("properties"):
        return raw_data

    # Mapping of column names to standardized variables
    standardized_mappings = {
        "participant_id": "participant_id",
        "age": "age",
        "sex": "biological_sex",
        "group": "participant_group",
        "handedness": "handedness",
    }

    # Categorical value mappings with controlled vocabulary URIs (SNOMED CT and PATO)
    # URIs are stored in shortened form for export (e.g., 'snomed:248153007')
    categorical_vocabularies = {
        "sex": {
            "M": {
                "label": "Male",
                "description": "Male biological sex",
                "uri": "snomed:248153007",
            },
            "F": {
                "label": "Female",
                "description": "Female biological sex",
                "uri": "snomed:248152002",
            },
            "O": {
                "label": "Other",
                "description": "Other biological sex",
                "uri": "snomed:447964000",
            },
        },
        "handedness": {
            "L": {
                "label": "Left",
                "description": "Left-handed",
                "uri": "snomed:87622008",
            },
            "R": {
                "label": "Right",
                "description": "Right-handed",
                "uri": "snomed:78791000",
            },
            "A": {
                "label": "Ambidextrous",
                "description": "Ambidextrous",
                "uri": "snomed:16022009",
            },
        },
    }

    # Augmented structure
    augmented = {"properties": {}}

    for col_name, col_data in raw_data.get("properties", {}).items():
        aug_col = {
            "description": col_data.get("description", ""),
            "original_data": col_data,
        }

        # Add standardized variable mapping
        if col_name in standardized_mappings:
            aug_col["standardized_variable"] = standardized_mappings[col_name]

        # Infer data type from Levels (if present, it's categorical)
        if "Levels" in col_data and isinstance(col_data["Levels"], dict):
            aug_col["data_type"] = "categorical"

            # Augment with vocabulary if available
            if col_name in categorical_vocabularies:
                aug_col["levels"] = {}
                for level_key, level_label in col_data["Levels"].items():
                    if level_key in categorical_vocabularies[col_name]:
                        aug_col["levels"][level_key] = categorical_vocabularies[
                            col_name
                        ][level_key]
                    else:
                        # Fallback: use provided label (no URI)
                        aug_col["levels"][level_key] = {
                            "label": (
                                level_label
                                if isinstance(level_label, str)
                                else str(level_key)
                            ),
                            "description": f"Value: {level_key}",
                            "uri": None,
                        }
            else:
                # No vocabulary available, use raw levels (no URIs)
                aug_col["levels"] = {
                    k: {"label": v, "description": f"Value: {k}", "uri": None}
                    for k, v in col_data["Levels"].items()
                }
        elif col_name in ["age"]:
            aug_col["data_type"] = "continuous"
            if "Units" in col_data:
                aug_col["unit"] = col_data["Units"]
        else:
            aug_col["data_type"] = "text"

        augmented["properties"][col_name] = aug_col

    return augmented


@app.route("/api/neurobagel/participants")
def neurobagel_participants():
    """Return NeuroBagel participants dictionary (cached) with augmented annotations.

    The frontend can call this to populate hierarchical suggestions for participants.json fields.
    Returns augmented data with:
    - Standardized variable mappings
    - Data type classifications
    - Categorical value vocabularies with URIs
    """
    data = fetch_neurobagel_participants()

    # If external fetch fails, use built-in dictionary
    if not data:
        # Use built-in NeuroBagel-compatible dictionary for common phenotypic variables
        data = {
            "properties": {
                "participant_id": {"Description": "A participant ID"},
                "age": {"Description": "Age of the participant", "Units": "years"},
                "sex": {
                    "Description": "Biological sex of the participant",
                    "Levels": {"M": "Male", "F": "Female", "O": "Other"},
                },
                "group": {
                    "Description": "Participant group or experimental condition",
                    "Levels": {},
                },
                "handedness": {
                    "Description": "Participant handedness",
                    "Levels": {"L": "Left", "R": "Right", "A": "Ambidextrous"},
                },
            }
        }

    # Augment raw data with standardized mappings and vocabularies
    augmented = augment_neurobagel_data(data)

    return jsonify(
        {
            "source": "neurobagel",
            "raw": data,
            "augmented": augmented,
            "note": (
                "Using built-in dictionary (external fetch failed)"
                if not fetch_neurobagel_participants()
                else "Using remote NeuroBagel dictionary"
            ),
        }
    )


def shorten_path(file_path, max_parts=3):
    """Shorten a file path to show only the last N parts with ellipsis"""
    if not file_path:
        return "General"

    parts = file_path.replace("\\", "/").split("/")
    if len(parts) <= max_parts:
        return "/".join(parts)

    return ".../" + "/".join(parts[-max_parts:])


def get_filename_from_path(file_path):
    """Extract just the filename from a path"""
    if not file_path:
        return "General"
    return os.path.basename(file_path)


# Global storage for validation results
validation_results = {}


@app.route("/")
def index():
    """Home page with tool selection"""
    return render_template("home.html")


@app.route("/validate")
def validate_dataset():
    """Dataset validation page with upload form"""
    # Get available schema versions
    schema_dir = os.path.join(os.path.dirname(__file__), "schemas")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
    try:
        from schema_manager import get_available_schema_versions

        available_versions = get_available_schema_versions(schema_dir)
    except Exception as e:
        print(f"Warning: Could not load schema versions: {e}")
        available_versions = ["stable"]

    return render_template("index.html", schema_versions=available_versions)


@app.route("/upload", methods=["POST"])
def upload_dataset():
    """Handle dataset upload and validation"""
    if "dataset" not in request.files:
        flash("No dataset uploaded", "error")
        return redirect(url_for("index"))

    files = request.files.getlist("dataset")
    if not files or (len(files) == 1 and files[0].filename == ""):
        flash("No files selected", "error")
        return redirect(url_for("index"))

    # Get schema version from form
    schema_version = request.form.get("schema_version", "stable")

    # Create temporary directory for processing
    temp_dir = tempfile.mkdtemp(prefix="prism_validator_")

    # Try to get metadata paths from JSON first (new method), fall back to list (old method)
    metadata_paths_json = request.form.get("metadata_paths_json")
    if metadata_paths_json:
        try:
            metadata_paths = json.loads(metadata_paths_json)
        except json.JSONDecodeError:
            metadata_paths = []
    else:
        metadata_paths = request.form.getlist("metadata_paths[]")

    try:
        # Check if this is a folder upload (multiple files) or ZIP upload (single file)
        if len(files) > 1 or (
            len(files) == 1 and not files[0].filename.lower().endswith(".zip")
        ):
            # Handle folder upload
            dataset_path = process_folder_upload(files, temp_dir, metadata_paths)
            filename = f"folder_upload_{len(files)}_files"
        else:
            # Handle ZIP upload
            file = files[0]
            filename = secure_filename(file.filename)
            if not filename.lower().endswith(".zip"):
                flash("Please upload a ZIP file or select a folder", "error")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return redirect(url_for("index"))

            dataset_path = process_zip_upload(file, temp_dir, filename)

        # DEBUG: Print dataset_path and sample files (excluding system files)
        print(f"📁 [UPLOAD] Validating dataset at: {dataset_path}")
        for root, dirs, files in os.walk(dataset_path):
            # Filter out system files from debug output
            try:
                filtered_files = [f for f in files if not is_system_file(f)]
            except NameError:
                # Fallback filtering
                filtered_files = [
                    f
                    for f in files
                    if not (
                        f.startswith(".")
                        or f in ["Thumbs.db", "ehthumbs.db", "Desktop.ini"]
                    )
                ]

            for file in filtered_files[:10]:
                print(f"   {os.path.relpath(os.path.join(root, file), dataset_path)}")
            if len(files) != len(filtered_files):
                print(f"   (+ {len(files) - len(filtered_files)} system files ignored)")
            break
        # Get BIDS options
        run_bids = request.form.get("run_bids") == "true"
        show_bids_warnings = request.form.get("bids_warnings") == "true"

        # Validate the dataset using core validator when available
        if callable(core_validate_dataset):
            issues, dataset_stats = core_validate_dataset(
                dataset_path, 
                verbose=True, 
                schema_version=schema_version,
                run_bids=run_bids
            )
        else:
            issues, dataset_stats = run_main_validator(
                dataset_path, 
                verbose=True, 
                schema_version=schema_version,
                run_bids=run_bids
            )

        # Filter BIDS warnings if requested
        if not show_bids_warnings:
            issues = [i for i in issues if not (i[0] == "WARNING" and "[BIDS]" in i[1])]

        results = format_validation_results(issues, dataset_stats, dataset_path)

        # Add timestamp, upload type info, and schema version
        from datetime import datetime

        results["timestamp"] = datetime.now().isoformat()
        results["upload_type"] = "structure_only"
        results["schema_version"] = schema_version

        # Check if manifest exists and add details
        manifest_path = os.path.join(dataset_path, ".upload_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            results["upload_manifest"] = {
                "metadata_files": len(manifest.get("uploaded_files", [])),
                "placeholder_files": len(manifest.get("placeholder_files", [])),
                "upload_mode": "DataLad-style (structure + metadata only)",
            }

        # DEBUG: Print summary to console
        print("📊 Validation complete:")
        print(f"   Total files: {results['summary']['total_files']}")
        print(f"   Valid files: {results['summary']['valid_files']}")
        print(f"   Invalid files: {results['summary']['invalid_files']}")
        print(f"   Total errors: {results['summary']['total_errors']}")

        # Store results globally (in production, use a database)
        result_id = f"result_{len(validation_results)}"
        validation_results[result_id] = {
            "results": results,
            "dataset_path": dataset_path,
            "temp_dir": temp_dir,
            "filename": filename,
        }

        return redirect(url_for("show_results", result_id=result_id))

    except Exception as e:
        # Clean up on error
        print(f"❌ [UPLOAD ERROR] {type(e).__name__}: {str(e)}")
        import traceback

        traceback.print_exc()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        flash(f"Error processing dataset: {str(e)}", "error")
        return redirect(url_for("index"))


def create_placeholder_content(file_path, extension):
    """Create informative placeholder content for data files (DataLad-style)"""
    filename = os.path.basename(file_path)

    # For JSON files, create valid JSON placeholders
    if extension.lower() == ".json":
        return json.dumps(
            {
                "_placeholder": True,
                "_upload_mode": "DataLad-style (structure + metadata only)",
                "_original_filename": filename,
                "_created": datetime.now().isoformat(),
                "_note": "This is a placeholder file. Original JSON was not uploaded to reduce transfer size.",
            },
            indent=2,
        )

    # For TSV files, create valid TSV placeholders
    elif extension.lower() == ".tsv":
        return f"# PLACEHOLDER TSV - DataLad-style Upload\n# Original filename: {filename}\n# Created: {datetime.now().isoformat()}\n_placeholder\ttrue\n"

    # For other file types, use text placeholder
    else:
        # Determine file type from extension
        file_type_map = {
            ".nii": "NIfTI neuroimaging data",
            ".nii.gz": "Compressed NIfTI neuroimaging data",
            ".png": "PNG image stimulus",
            ".jpg": "JPEG image stimulus",
            ".jpeg": "JPEG image stimulus",
            ".tiff": "TIFF image data",
            ".mp4": "MP4 video stimulus",
            ".avi": "AVI video data",
            ".mov": "QuickTime video",
            ".eeg": "EEG raw data",
            ".dat": "Binary data file",
            ".fif": "Neuromag/MNE data",
            ".mat": "MATLAB data file",
            ".edf": "European Data Format (EEG/Physio)",
            ".bdf": "BioSemi Data Format",
            ".set": "EEGLAB dataset info",
            ".fdt": "EEGLAB data file",
        }

        file_type = file_type_map.get(extension, f"{extension} data file")

        placeholder = f"""# PLACEHOLDER FILE - DataLad-style Upload
# This is a placeholder for the original data file that was not uploaded
# to reduce transfer size and processing time.

Original filename: {filename}
File type: {file_type}
Upload mode: Structure-only validation
Created: {datetime.now().isoformat()}

# The validator can still check:
# - File naming conventions
# - Directory structure
# - Metadata completeness (via JSON sidecars)
# - BIDS compliance

# Note: Full content validation requires the complete dataset.
"""
        return placeholder


def detect_dataset_prefix(all_paths):
    """Detect a common leading folder that should be stripped from uploaded paths."""
    sanitized_parts = []
    has_root_level_files = False
    for path in all_paths or []:
        if not path:
            continue
        parts = [part for part in path.replace("\\", "/").split("/") if part]
        if not parts:
            continue
        if len(parts) == 1:
            has_root_level_files = True
        sanitized_parts.append(parts)
    if has_root_level_files or not sanitized_parts:
        return None
    first_components = {parts[0] for parts in sanitized_parts}
    if len(first_components) != 1:
        return None
    candidate = first_components.pop()
    restricted_names = {
        "image",
        "audio",
        "movie",
        "survey",
        "eyetracking",
        "physiological",
        "dataset",
    }
    if candidate.startswith(("sub-", "ses-")) or candidate in restricted_names:
        return None
    has_dataset_description = any(
        len(parts) >= 2
        and parts[0] == candidate
        and parts[1] == "dataset_description.json"
        for parts in sanitized_parts
    )
    has_subject_dirs = any(
        len(parts) >= 2 and parts[0] == candidate and parts[1].startswith("sub-")
        for parts in sanitized_parts
    )
    if not (has_dataset_description or has_subject_dirs):
        return None
    return candidate


def normalize_relative_path(path, prefix_to_strip):
    """Normalise an uploaded path so it is safe and relative to the dataset root."""
    if not path:
        return None
    cleaned = path.replace("\\", "/").lstrip("/")
    if prefix_to_strip:
        prefix = prefix_to_strip.strip("/")
        if cleaned.startswith(prefix + "/"):
            cleaned = cleaned[len(prefix) + 1 :]
    normalized = os.path.normpath(cleaned)
    normalized = normalized.replace("\\", "/")
    if normalized in ("", "."):  # Directory only
        return None
    if normalized.startswith(".."):
        return None
    return normalized


def process_folder_upload(files, temp_dir, metadata_paths=None):
    """Process uploaded folder files and recreate directory structure (DataLad-style)

    DataLad-inspired approach: Upload only structure and metadata, create placeholders
    for large data files. This allows full dataset validation without transferring GB of data.
    """
    dataset_root = os.path.join(temp_dir, "dataset")
    os.makedirs(dataset_root, exist_ok=True)

    processed_count = 0
    skipped_count = 0
    manifest = {
        "uploaded_files": [],
        "placeholder_files": [],
        "upload_type": "structure_only",
        "timestamp": datetime.now().isoformat(),
    }

    # Get the list of all files (including skipped ones) from form data
    all_files_json = request.form.get("all_files")
    all_files_list = json.loads(all_files_json) if all_files_json else []
    metadata_paths = metadata_paths or []

    candidate_paths = list(all_files_list or [])
    if metadata_paths:
        candidate_paths.extend(metadata_paths)
    else:
        candidate_paths.extend(
            [f.filename for f in files if getattr(f, "filename", None)]
        )

    prefix_to_strip = detect_dataset_prefix(candidate_paths)
    if prefix_to_strip:
        print(f"📁 [UPLOAD] Stripping leading folder: {prefix_to_strip}")

    # Create a set of uploaded file paths for quick lookup
    uploaded_paths = set()

    if metadata_paths and len(metadata_paths) != len(files):
        print(
            f"⚠️  Metadata path count ({len(metadata_paths)}) does not match uploaded files ({len(files)})."
        )

    for index, file in enumerate(files):
        original_path = (
            metadata_paths[index]
            if index < len(metadata_paths)
            else getattr(file, "filename", "")
        )
        if not original_path:
            continue
        normalized_path = normalize_relative_path(original_path, prefix_to_strip)
        if not normalized_path:
            continue

        # Skip system files (like .DS_Store, Thumbs.db, etc.)
        filename = os.path.basename(normalized_path)
        try:
            if is_system_file(filename):
                continue
        except NameError:
            if filename.startswith(".") and filename in [
                ".DS_Store",
                "._.DS_Store",
                ".Spotlight-V100",
                ".Trashes",
            ]:
                continue
            if filename in ["Thumbs.db", "ehthumbs.db", "Desktop.ini"]:
                continue

        uploaded_paths.add(normalized_path)
        file_path = os.path.join(dataset_root, *normalized_path.split("/"))
        target_dir = os.path.dirname(file_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        file.save(file_path)
        processed_count += 1

        manifest["uploaded_files"].append(
            {
                "path": normalized_path,
                "size": file.content_length or 0,
                "type": "metadata",
            }
        )

    # Create smart placeholders for all files that weren't uploaded
    for relative_path in all_files_list:
        normalized_path = normalize_relative_path(relative_path, prefix_to_strip)
        if not normalized_path or normalized_path in uploaded_paths:
            continue

        filename = os.path.basename(normalized_path)
        try:
            if is_system_file(filename):
                continue
        except NameError:
            if filename.startswith(".") and filename in [
                ".DS_Store",
                "._.DS_Store",
                ".Spotlight-V100",
                ".Trashes",
            ]:
                continue
            if filename in ["Thumbs.db", "ehthumbs.db", "Desktop.ini"]:
                continue

        file_path = os.path.join(dataset_root, *normalized_path.split("/"))
        target_dir = os.path.dirname(file_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        lower_path = normalized_path.lower()
        if lower_path.endswith(".nii.gz"):
            ext = ".nii.gz"
        else:
            _, ext = os.path.splitext(lower_path)
        placeholder_content = create_placeholder_content(normalized_path, ext)
        with open(file_path, "w") as f:
            f.write(placeholder_content)
        skipped_count += 1

        manifest["placeholder_files"].append(
            {"path": normalized_path, "extension": ext, "type": "placeholder"}
        )

    # Save manifest file for debugging and transparency
    manifest_path = os.path.join(dataset_root, ".upload_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"📁 Processed {processed_count} metadata files, created {skipped_count} placeholders for data files"
    )
    print("📁 [UPLOAD] File tree in temp_dir after upload:")
    for root, dirs, files in os.walk(dataset_root):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), dataset_root)
            print(f"   {rel_path}")
    return dataset_root


def process_zip_upload(file, temp_dir, filename):
    """Process uploaded ZIP file

    Extracts only metadata files from ZIP to reduce processing time and storage.
    """
    file_path = os.path.join(temp_dir, filename)
    file.save(file_path)

    processed_count = 0
    skipped_count = 0

    # Extract ZIP file selectively
    with zipfile.ZipFile(file_path, "r") as zip_ref:
        for zip_info in zip_ref.namelist():
            # Skip directories
            if zip_info.endswith("/"):
                continue

            # Check file extension
            _, ext = os.path.splitext(zip_info.lower())
            if ext == ".gz" and zip_info.lower().endswith(".nii.gz"):
                ext = ".nii.gz"

            # Extract metadata files, skip large data files
            if ext in METADATA_EXTENSIONS or ext == "":
                zip_ref.extract(zip_info, temp_dir)
                processed_count += 1
            elif ext in SKIP_EXTENSIONS:
                # Create empty placeholder
                extract_path = os.path.join(temp_dir, zip_info)
                os.makedirs(os.path.dirname(extract_path), exist_ok=True)
                with open(extract_path, "w") as f:
                    f.write("")
                skipped_count += 1

    print(
        f"📦 Extracted {processed_count} metadata files, skipped {skipped_count} data files from ZIP"
    )

    # Find the actual dataset directory (might be nested)
    return find_dataset_root(temp_dir)


@app.route("/validate_folder", methods=["POST"])
def validate_folder():
    """Handle local folder validation"""
    folder_path = request.form.get("folder_path", "").strip()

    if not folder_path:
        flash("Please provide a folder path", "error")
        return redirect(url_for("index"))

    if not os.path.exists(folder_path):
        flash("Folder does not exist", "error")
        return redirect(url_for("index"))

    if not os.path.isdir(folder_path):
        flash("Path is not a directory", "error")
        return redirect(url_for("index"))

    # Get schema version from form
    schema_version = request.form.get("schema_version", "stable")

    try:
        # Print validation start info to terminal
        print(f"\n📁 [VALIDATE_FOLDER] Validating local directory: {folder_path}")

        # Count files for debug output
        file_count = 0
        for root, dirs, files in os.walk(folder_path):
            file_count += len([f for f in files if not is_system_file(f)])
        print(f"   Found {file_count} non-system files in directory")

        # Get BIDS options
        run_bids = request.form.get("run_bids") == "true"
        show_bids_warnings = request.form.get("bids_warnings") == "true"

        # Use the core validator when available for direct integration
        if callable(core_validate_dataset):
            issues, stats = core_validate_dataset(
                folder_path, 
                verbose=True, 
                schema_version=schema_version,
                run_bids=run_bids
            )
        else:
            issues, stats = run_main_validator(
                folder_path, 
                verbose=True, 
                schema_version=schema_version,
                run_bids=run_bids
            )

        # Filter BIDS warnings if requested
        if not show_bids_warnings:
            issues = [i for i in issues if not (i[0] == "WARNING" and "[BIDS]" in i[1])]

        # Format results for web display
        formatted_results = format_validation_results(issues, stats, folder_path)
        formatted_results["schema_version"] = schema_version

        # Print validation results to terminal
        print("📊 [VALIDATE_FOLDER] Validation complete:")
        print(f"   Total files: {formatted_results['summary']['total_files']}")
        print(f"   Valid files: {formatted_results['summary']['valid_files']}")
        print(f"   Invalid files: {formatted_results['summary']['invalid_files']}")
        print(f"   Errors: {formatted_results['summary']['total_errors']}")
        print(f"   Warnings: {formatted_results['summary']['total_warnings']}")

        # Store results
        result_id = f"result_{len(validation_results)}"
        validation_results[result_id] = {
            "results": formatted_results,
            "dataset_path": folder_path,
            "temp_dir": None,  # No temp dir for local folders
            "filename": os.path.basename(folder_path),
        }

        return redirect(url_for("show_results", result_id=result_id))

    except Exception as e:
        flash(f"Error validating dataset: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/results/<result_id>")
def show_results(result_id):
    """Display validation results"""
    if result_id not in validation_results:
        flash("Results not found", "error")
        return redirect(url_for("index"))

    data = validation_results[result_id]
    results = data["results"]

    # Get dataset stats if available
    dataset_stats = None
    stats_obj = results.get("dataset_stats")
    if stats_obj:
        try:
            session_entries = getattr(stats_obj, "sessions", set()) or set()
            unique_sessions = set()
            for entry in session_entries:
                if isinstance(entry, str) and "/" in entry:
                    unique_sessions.add(entry.split("/", 1)[1])
                elif entry:
                    unique_sessions.add(entry)

            dataset_stats = {
                "total_subjects": len(getattr(stats_obj, "subjects", [])),
                "total_sessions": len(unique_sessions),
                "modalities": getattr(stats_obj, "modalities", {}),
                "tasks": sorted(getattr(stats_obj, "tasks", [])),
                "total_files": getattr(stats_obj, "total_files", 0),
                "sidecar_files": getattr(stats_obj, "sidecar_files", 0),
            }
        except Exception as stats_error:
            print(f"⚠️  Failed to prepare dataset stats for display: {stats_error}")

    return render_template(
        "results.html",
        results=results,
        result_id=result_id,
        filename=data["filename"],
        dataset_stats=dataset_stats,
        shorten_path=shorten_path,
        get_filename_from_path=get_filename_from_path,
        get_error_documentation_url=get_error_documentation_url,
    )


@app.route("/download_report/<result_id>")
def download_report(result_id):
    """Download validation report as JSON"""
    if result_id not in validation_results:
        flash("Results not found", "error")
        return redirect(url_for("index"))

    data = validation_results[result_id]
    results = data["results"]

    # Create JSON report
    report = {
        "dataset": data["filename"],
        "validation_timestamp": results.get("timestamp", ""),
        "summary": {
            "total_files": len(results.get("valid_files", []))
            + len(results.get("invalid_files", [])),
            "valid_files": len(results.get("valid_files", [])),
            "invalid_files": len(results.get("invalid_files", [])),
            "total_errors": len(results.get("errors", [])),
            "total_warnings": len(results.get("warnings", [])),
        },
        "results": results,
    }

    # Create in-memory file
    output = io.BytesIO()
    output.write(json.dumps(report, indent=2).encode("utf-8"))
    output.seek(0)

    return send_file(
        output,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"validation_report_{data['filename']}.json",
    )


@app.route("/cleanup/<result_id>")
def cleanup(result_id):
    """Clean up temporary files"""
    if result_id in validation_results:
        data = validation_results[result_id]
        if data["temp_dir"] and os.path.exists(data["temp_dir"]):
            shutil.rmtree(data["temp_dir"], ignore_errors=True)
        del validation_results[result_id]

    flash("Results cleaned up", "success")
    return redirect(url_for("index"))


@app.route("/api/validate", methods=["POST"])
def api_validate():
    """API endpoint for validation (for programmatic access)"""
    try:
        data = request.get_json()
        if not data or "dataset_path" not in data:
            return jsonify({"error": "Missing dataset_path parameter"}), 400

        dataset_path = data["dataset_path"]
        if not os.path.exists(dataset_path):
            return jsonify({"error": "Dataset path does not exist"}), 400

        # Use main validator script
        issues, stats = run_main_validator(dataset_path, verbose=False)
        results = format_validation_results(issues, stats, dataset_path)

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def find_dataset_root(extract_dir):
    """Find the actual dataset root directory after extraction"""
    # Look for dataset_description.json or typical BIDS structure
    for root, dirs, files in os.walk(extract_dir):
        if "dataset_description.json" in files:
            return root
        # Look for subject directories
        if any(d.startswith("sub-") for d in dirs):
            return root

    # If no clear dataset structure, return the extraction directory
    return extract_dir


def find_free_port(start_port):
    """Find a free port starting from start_port"""
    import socket
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
            port += 1
    return start_port

def main():
    """Run the web application"""
    import argparse

    parser = argparse.ArgumentParser(description="Prism-Validator Web Interface")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port to bind to (default: 5001, avoiding macOS Control Center on port 5000)",
    )
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument(
        "--public",
        action="store_true",
        help="Allow external connections (sets host to 0.0.0.0)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open browser",
    )

    args = parser.parse_args()

    host = "0.0.0.0" if args.public else args.host
    
    # Find a free port if the default one is taken
    port = args.port
    if not args.public: # Only auto-find port for local binding
        port = find_free_port(args.port)
        if port != args.port:
            print(f"ℹ️  Port {args.port} is in use, using {port} instead")

    display_host = "localhost" if host == "127.0.0.1" else host
    url = f"http://{display_host}:{port}"

    print("🌐 Starting Prism-Validator Web Interface")
    print(f"🔗 URL: {url}")
    if args.public:
        print("⚠️  Warning: Running in public mode - accessible from other computers")
    print("💡 Press Ctrl+C to stop the server")
    print()

    # Open browser in a separate thread to avoid blocking the Flask server
    if not args.no_browser:

        def open_browser():
            import time

            time.sleep(1)  # Wait for server to start
            try:
                webbrowser.open(url)
                print("✅ Browser opened automatically")
            except Exception as e:
                print(f"ℹ️  Could not open browser automatically: {e}")
                print(f"   Please visit {url} manually")

        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

    if args.debug:
        app.run(host=host, port=port, debug=True)
    else:
        try:
            from waitress import serve
            print(f"🚀 Running with Waitress server on {host}:{port}")
            serve(app, host=host, port=port)
        except ImportError:
            print("⚠️  Waitress not installed, falling back to Flask development server")
            app.run(host=host, port=port)
            app.run(host=host, port=args.port, debug=False)


@app.route("/survey-generator")
def survey_generator():
    """Survey generator page"""
    return render_template("survey_generator.html")


# ==========================================
# Survey Library Management Routes
# ==========================================


@app.route("/library")
def library_view():
    """View the survey library management page"""
    if not survey_manager:
        return "Survey Manager not initialized", 500
    
    surveys = survey_manager.list_surveys()
    return render_template("library.html", surveys=surveys)


@app.route("/library/edit/<filename>")
def edit_survey(filename):
    """Edit a survey draft"""
    if not survey_manager:
        return "Survey Manager not initialized", 500
    
    try:
        content = survey_manager.get_draft_content(filename)
        return render_template("library_editor.html", filename=filename, content=content)
    except FileNotFoundError:
        return "Draft not found", 404
    except Exception as e:
        return str(e), 500


@app.route("/library/api/draft/<filename>", methods=["POST"])
def create_draft(filename):
    """Create a new draft from master"""
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500
    
    try:
        survey_manager.create_draft(filename)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/library/api/draft/<filename>", methods=["DELETE"])
def discard_draft(filename):
    """Discard a draft"""
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500
    
    try:
        survey_manager.discard_draft(filename)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/library/api/save/<filename>", methods=["POST"])
def save_draft(filename):
    """Save content to draft"""
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500
    
    try:
        content = request.json
        survey_manager.save_draft(filename, content)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/library/api/publish/<filename>", methods=["POST"])
def publish_draft(filename):
    """Submit draft as merge request"""
    if not survey_manager:
        return jsonify({"error": "Survey Manager not initialized"}), 500
    
    try:
        survey_manager.publish_draft(filename)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/browse-folder")
def browse_folder():
    """Open a system dialog to select a folder"""
    folder_path = ""
    try:
        if sys.platform == "darwin":
            # Use AppleScript on macOS to avoid Tkinter threading issues
            import subprocess

            try:
                script = "POSIX path of (choose folder)"
                # Run osascript
                result = subprocess.check_output(
                    ["osascript", "-e", script], stderr=subprocess.STDOUT
                )
                folder_path = result.decode("utf-8").strip()
            except subprocess.CalledProcessError:
                # User cancelled
                folder_path = ""
        else:
            # Fallback to Tkinter for Windows/Linux
            # Note: This might still have threading issues on some systems
            import tkinter as tk
            from tkinter import filedialog

            # Create a root window and hide it
            root = tk.Tk()
            root.withdraw()

            # Make it appear on top
            root.attributes("-topmost", True)

            folder_path = filedialog.askdirectory()

            root.destroy()

        if folder_path:
            return jsonify({"path": folder_path})
        else:
            return jsonify({"path": ""})  # User cancelled

    except Exception as e:
        print(f"Error opening file dialog: {e}")
        return (
            jsonify(
                {"error": "Could not open file dialog. Please enter path manually."}
            ),
            500,
        )


@app.route("/api/list-library-files")
def list_library_files():
    """List JSON files in a user-specified library path"""
    library_path = request.args.get("path")
    if not library_path:
        return jsonify({"error": "Path parameter is required"}), 400

    if not os.path.exists(library_path):
        return jsonify({"error": "Path does not exist"}), 404

    if not os.path.isdir(library_path):
        return jsonify({"error": "Path is not a directory"}), 400

    try:
        files = []
        for f in os.listdir(library_path):
            if f.endswith(".json") and not f.startswith("."):
                full_path = os.path.join(library_path, f)
                # Try to read description and metadata
                desc = ""
                original_name = ""
                questions = []
                try:
                    with open(full_path, "r") as jf:
                        data = json.load(jf)
                        study = data.get("Study", {})
                        desc = study.get("Description", "")
                        original_name = study.get("OriginalName", "")
                        if not desc:
                            desc = data.get("TaskName", "")

                        # Extract questions
                        questions = []
                        
                        # Check for "Questions" key (New Format)
                        if "Questions" in data and isinstance(data["Questions"], dict):
                            for k, v in data["Questions"].items():
                                q_desc = ""
                                q_levels = None
                                q_units = None
                                q_min = None
                                q_max = None
                                q_warn_min = None
                                q_warn_max = None
                                q_type = None
                                
                                if isinstance(v, dict):
                                    q_desc = v.get("Description", "")
                                    q_levels = v.get("Levels")
                                    q_units = v.get("Units")
                                    q_min = v.get("MinValue")
                                    q_max = v.get("MaxValue")
                                    q_warn_min = v.get("WarnMinValue")
                                    q_warn_max = v.get("WarnMaxValue")
                                    q_type = v.get("DataType")
                                    
                                questions.append(
                                    {
                                        "id": k, 
                                        "description": q_desc, 
                                        "levels": q_levels,
                                        "units": q_units,
                                        "min": q_min,
                                        "max": q_max,
                                        "warn_min": q_warn_min,
                                        "warn_max": q_warn_max,
                                        "type": q_type
                                    }
                                )
                        else:
                            # Fallback for Old Format (Flat structure)
                            reserved = [
                                "Technical",
                                "Study",
                                "Metadata",
                                "Categories",
                                "TaskName",
                                "Name",
                                "BIDSVersion",
                                "Description",
                                "URL",
                                "License",
                                "Authors",
                                "Acknowledgements",
                                "References",
                                "Funding"
                            ]
                            for k, v in data.items():
                                if k not in reserved:
                                    q_desc = ""
                                    q_levels = None
                                    q_units = None
                                    q_min = None
                                    q_max = None
                                    q_warn_min = None
                                    q_warn_max = None
                                    q_type = None
                                    
                                    if isinstance(v, dict):
                                        q_desc = v.get("Description", "")
                                        q_levels = v.get("Levels")
                                        q_units = v.get("Units")
                                        q_min = v.get("MinValue")
                                        q_max = v.get("MaxValue")
                                        q_warn_min = v.get("WarnMinValue")
                                        q_warn_max = v.get("WarnMaxValue")
                                        q_type = v.get("DataType")
                                        
                                    questions.append(
                                        {
                                            "id": k, 
                                            "description": q_desc, 
                                            "levels": q_levels,
                                            "units": q_units,
                                            "min": q_min,
                                            "max": q_max,
                                            "warn_min": q_warn_min,
                                            "warn_max": q_warn_max,
                                            "type": q_type
                                        }
                                    )
                except:
                    pass

                files.append(
                    {
                        "filename": f,
                        "path": full_path,
                        "description": desc,
                        "original_name": original_name,
                        "questions": questions,
                        "question_count": len(questions),
                    }
                )

        return jsonify({"files": sorted(files, key=lambda x: x["filename"])})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate-lss", methods=["POST"])
def generate_lss_endpoint():
    """Generate LSS from selected JSON files"""
    if not generate_lss:
        return jsonify({"error": "LSS exporter not available"}), 500

    try:
        data = request.get_json()
        if not data or "files" not in data:
            return jsonify({"error": "No files selected"}), 400

        files = data["files"]
        if not files:
            return jsonify({"error": "File list is empty"}), 400

        # Verify files exist
        valid_files = []
        for item in files:
            f_path = item
            if isinstance(item, dict):
                f_path = item.get("path")

            if f_path and os.path.exists(f_path):
                valid_files.append(item)
            else:
                print(f"Warning: File not found: {f_path}")

        if not valid_files:
            return jsonify({"error": "No valid files found"}), 404

        # Generate LSS content
        # We return it as a downloadable file

        # Create a temporary file
        fd, temp_path = tempfile.mkstemp(suffix=".lss")
        os.close(fd)

        generate_lss(valid_files, temp_path)

        return send_file(
            temp_path,
            as_attachment=True,
            download_name="survey_export.lss",
            mimetype="application/xml",
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    main()
