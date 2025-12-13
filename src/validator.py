"""
Core validation logic for prism-validator
"""

import os
import re
import json
import csv
from datetime import datetime
from jsonschema import validate, ValidationError
from schema_manager import validate_schema_version
from cross_platform import (
    normalize_path,
    safe_path_join,
    CrossPlatformFile,
    validate_filename_cross_platform,
)

# Modality patterns
MODALITY_PATTERNS = {
    "survey": r".+\.tsv$",
    "biometrics": r".+\.tsv$",
    "events": r".+_events\.tsv$",
    "physio": r".+_ecg\.edf$",
    # MRI submodalities
    "anat": r".+_(T1w|T2w|T2star|FLAIR|PD|PDw|T1map|T2map)\.nii(\.gz)?$",
    "func": r".+(_bold\.nii(\.gz)?|_sbref\.nii(\.gz)?|_(events|physio|stim)\.tsv(\.gz)?)$",
    "fmap": r".+_(magnitude1|magnitude2|phasediff|fieldmap|epi)\.nii(\.gz)?$",
    "dwi": r".+_dwi(\.nii(\.gz)?|\.bvec|\.bval)$",
}

# BIDS naming patterns
BIDS_REGEX = re.compile(
    r"^sub-[a-zA-Z0-9]+"
    r"(_ses-[a-zA-Z0-9]+)?"
    r"(_(task|survey|biometrics)-[a-zA-Z0-9]+)?"
    r"(_run-[0-9]+)?"
)

MRI_SUFFIX_REGEX = re.compile(
    r"_(T1w|T2w|T2star|FLAIR|PD|PDw|T1map|T2map|bold|dwi|magnitude1|magnitude2|phasediff|fieldmap|epi|sbref)$"
)

# File extensions that need special handling
COMPOUND_EXTS = (".nii.gz", ".tsv.gz", ".edf.gz")


def split_compound_ext(filename):
    """Return (stem, ext) and handle compound extensions like .nii.gz."""
    if any(filename.endswith(ext) for ext in COMPOUND_EXTS):
        for ext in COMPOUND_EXTS:
            if filename.endswith(ext):
                stem = filename[: -len(ext)]
                return stem, ext
    base, ext = os.path.splitext(filename)
    return base, ext


def derive_sidecar_path(file_path):
    """Derive the JSON sidecar path for a data file."""
    file_path = normalize_path(file_path)
    dirname = os.path.dirname(file_path)
    fname = os.path.basename(file_path)
    stem, _ext = split_compound_ext(fname)
    return safe_path_join(dirname, f"{stem}.json")


def _extract_entity_value(stem, key):
    match = re.search(rf"_{key}-([a-zA-Z0-9]+)", stem)
    if match:
        return match.group(1)
    return None


def resolve_sidecar_path(file_path, root_dir):
    """Return best-matching sidecar path, supporting dataset-level survey sidecars."""
    candidate = derive_sidecar_path(file_path)
    if os.path.exists(candidate):
        return candidate

    stem, _ext = split_compound_ext(os.path.basename(file_path))
    suffix = ""
    if "_" in stem:
        suffix = stem.split("_")[-1]

    survey_value = _extract_entity_value(stem, "survey")
    biometrics_value = _extract_entity_value(stem, "biometrics")
    task_value = _extract_entity_value(stem, "task")

    label_candidates = []
    if survey_value:
        label_candidates.append(("survey", survey_value))
    if biometrics_value:
        label_candidates.append(("biometrics", biometrics_value))
    if task_value:
        label_candidates.append(("task", task_value))
        if not survey_value and not biometrics_value:
            label_candidates.append(("survey", task_value))
            label_candidates.append(("biometrics", task_value))

    search_dirs = [
        root_dir,
        safe_path_join(root_dir, "surveys"),
        safe_path_join(root_dir, "biometrics"),
    ]

    for prefix, value in label_candidates:
        base_name = f"{prefix}-{value}"
        suffix_part = f"_{suffix}" if suffix and suffix != base_name else ""
        file_name = f"{base_name}{suffix_part}.json"
        for directory in search_dirs:
            if not directory:
                continue
            dataset_candidate = safe_path_join(directory, file_name)
            if os.path.exists(dataset_candidate):
                return dataset_candidate

    return candidate


class DatasetValidator:
    """Main dataset validation class"""

    def __init__(self, schemas=None):
        self.schemas = schemas or {}

    def validate_data_content(self, file_path, modality, root_dir):
        """Validate data content against constraints in sidecar"""
        issues = []

        # Only validate content for tabular data modalities
        if modality not in ["survey", "biometrics"]:
            return issues

        sidecar_path = resolve_sidecar_path(file_path, root_dir)
        if not os.path.exists(sidecar_path):
            # Missing sidecar is already reported by validate_sidecar
            return issues

        try:
            # Check for empty file
            if os.path.getsize(file_path) == 0:
                return [
                    (
                        "ERROR",
                        f"File {os.path.basename(file_path)} is empty. If data is missing, please delete the file.",
                    )
                ]

            # Load sidecar
            sidecar_content = CrossPlatformFile.read_text(sidecar_path)
            sidecar_data = json.loads(sidecar_content)

            # Read TSV file
            with open(file_path, "r", newline="", encoding="utf-8") as tsvfile:
                reader = csv.DictReader(tsvfile, delimiter="\t")

                if not reader.fieldnames:
                    return [
                        (
                            "ERROR",
                            f"File {os.path.basename(file_path)} is not a valid TSV (no header found).",
                        )
                    ]

                row_count = 0
                for row_idx, row in enumerate(
                    reader, start=2
                ):  # start=2 for 1-based line number (header is 1)
                    row_count += 1

                    # Check for completely empty row (all values are empty strings)
                    if all(v is None or v.strip() == "" for v in row.values()):
                        issues.append(
                            (
                                "WARNING",
                                f"{os.path.basename(file_path)} line {row_idx}: Row contains only empty values. Use 'n/a' for missing data, or delete the file if no data exists.",
                            )
                        )
                        continue

                    for col_name, value in row.items():
                        if col_name in sidecar_data:
                            col_def = sidecar_data[col_name]

                            # Skip empty values
                            if value is None or value.strip() == "" or value == "n/a":
                                continue

                            # Check AllowedValues or Levels
                            allowed = None
                            if "AllowedValues" in col_def:
                                allowed = [str(x) for x in col_def["AllowedValues"]]
                            elif "Levels" in col_def:
                                levels = col_def["Levels"]
                                level_keys = list(levels.keys())

                                # If level keys are numeric endpoints (e.g., {"0": "...", "5": "..."})
                                # allow the full inclusive integer range to avoid over-rejecting mid-scale values.
                                numeric_level_keys = []
                                try:
                                    numeric_level_keys = [int(float(k)) for k in level_keys]
                                except ValueError:
                                    numeric_level_keys = []

                                if numeric_level_keys:
                                    min_level = min(numeric_level_keys)
                                    max_level = max(numeric_level_keys)

                                    # Only expand when we clearly have an ordinal numeric scale that might omit midpoints.
                                    # If the provided keys already cover every integer in the range, keep them as-is.
                                    full_range = [str(i) for i in range(min_level, max_level + 1)]
                                    if set(full_range).issuperset(set(level_keys)):
                                        allowed = full_range
                                    else:
                                        allowed = level_keys
                                else:
                                    allowed = level_keys

                            if allowed:
                                if value not in allowed:
                                    issues.append(
                                        (
                                            "ERROR",
                                            f"{os.path.basename(file_path)} line {row_idx}: Value '{value}' for '{col_name}' is not in allowed values: {allowed}",
                                        )
                                    )

                            # Check DataType
                            if "DataType" in col_def:
                                dtype = col_def["DataType"]
                                if dtype == "integer":
                                    try:
                                        # Check if it's a valid integer (e.g. "5", "5.0" might be acceptable depending on strictness, but usually "5")
                                        # Let's be strict: must be parseable as int and str representation matches or float is integer
                                        float_val = float(value)
                                        if not float_val.is_integer():
                                            issues.append(
                                                (
                                                    "ERROR",
                                                    f"{os.path.basename(file_path)} line {row_idx}: Value '{value}' for '{col_name}' is not a valid integer",
                                                )
                                            )
                                    except ValueError:
                                        issues.append(
                                            (
                                                "ERROR",
                                                f"{os.path.basename(file_path)} line {row_idx}: Value '{value}' for '{col_name}' is not a valid integer",
                                            )
                                        )
                                elif dtype == "float":
                                    try:
                                        float(value)
                                    except ValueError:
                                        issues.append(
                                            (
                                                "ERROR",
                                                f"{os.path.basename(file_path)} line {row_idx}: Value '{value}' for '{col_name}' is not a valid float",
                                            )
                                        )
                                elif dtype == "date":
                                    valid_date = False
                                    date_val = None
                                    formats = [
                                        "%Y-%m-%d",
                                        "%Y-%m-%d %H:%M",
                                        "%Y-%m-%d %H:%M:%S",
                                    ]

                                    for fmt in formats:
                                        try:
                                            date_val = datetime.strptime(value, fmt)
                                            valid_date = True
                                            break
                                        except ValueError:
                                            continue

                                    if valid_date:
                                        if date_val > datetime.now():
                                            issues.append(
                                                (
                                                    "WARNING",
                                                    f"{os.path.basename(file_path)} line {row_idx}: Date '{value}' for '{col_name}' is in the future",
                                                )
                                            )
                                        if date_val.year < 1900:
                                            issues.append(
                                                (
                                                    "WARNING",
                                                    f"{os.path.basename(file_path)} line {row_idx}: Date '{value}' for '{col_name}' is before 1900",
                                                )
                                            )
                                    else:
                                        issues.append(
                                            (
                                                "ERROR",
                                                f"{os.path.basename(file_path)} line {row_idx}: Value '{value}' for '{col_name}' is not a valid date (YYYY-MM-DD [HH:MM[:SS]])",
                                            )
                                        )

                            # Check Units="date" if DataType is missing
                            elif col_def.get("Units") == "date":
                                valid_date = False
                                date_val = None
                                formats = [
                                    "%Y-%m-%d",
                                    "%Y-%m-%d %H:%M",
                                    "%Y-%m-%d %H:%M:%S",
                                ]

                                for fmt in formats:
                                    try:
                                        date_val = datetime.strptime(value, fmt)
                                        valid_date = True
                                        break
                                    except ValueError:
                                        continue

                                if valid_date:
                                    if date_val > datetime.now():
                                        issues.append(
                                            (
                                                "WARNING",
                                                f"{os.path.basename(file_path)} line {row_idx}: Date '{value}' for '{col_name}' is in the future",
                                            )
                                        )
                                    if date_val.year < 1900:
                                        issues.append(
                                            (
                                                "WARNING",
                                                f"{os.path.basename(file_path)} line {row_idx}: Date '{value}' for '{col_name}' is before 1900",
                                            )
                                        )
                                else:
                                    issues.append(
                                        (
                                            "ERROR",
                                            f"{os.path.basename(file_path)} line {row_idx}: Value '{value}' for '{col_name}' is not a valid date (YYYY-MM-DD [HH:MM[:SS]])",
                                        )
                                    )

                            # Check MinValue/MaxValue/WarnMinValue/WarnMaxValue
                            if any(
                                k in col_def
                                for k in [
                                    "MinValue",
                                    "MaxValue",
                                    "WarnMinValue",
                                    "WarnMaxValue",
                                ]
                            ):
                                try:
                                    num_val = float(value)

                                    if "MinValue" in col_def:
                                        min_val = float(col_def["MinValue"])
                                        if num_val < min_val:
                                            issues.append(
                                                (
                                                    "ERROR",
                                                    f"{os.path.basename(file_path)} line {row_idx}: Value {num_val} for '{col_name}' is less than MinValue {min_val}",
                                                )
                                            )

                                    if "MaxValue" in col_def:
                                        max_val = float(col_def["MaxValue"])
                                        if num_val > max_val:
                                            issues.append(
                                                (
                                                    "ERROR",
                                                    f"{os.path.basename(file_path)} line {row_idx}: Value {num_val} for '{col_name}' is greater than MaxValue {max_val}",
                                                )
                                            )

                                    if "WarnMinValue" in col_def:
                                        warn_min_val = float(col_def["WarnMinValue"])
                                        if num_val < warn_min_val:
                                            issues.append(
                                                (
                                                    "WARNING",
                                                    f"{os.path.basename(file_path)} line {row_idx}: Value {num_val} for '{col_name}' is less than WarnMinValue {warn_min_val}",
                                                )
                                            )

                                    if "WarnMaxValue" in col_def:
                                        warn_max_val = float(col_def["WarnMaxValue"])
                                        if num_val > warn_max_val:
                                            issues.append(
                                                (
                                                    "WARNING",
                                                    f"{os.path.basename(file_path)} line {row_idx}: Value {num_val} for '{col_name}' is greater than WarnMaxValue {warn_max_val}",
                                                )
                                            )

                                except ValueError:
                                    # Only report if we expected a number (Min/Max present) but got non-number
                                    issues.append(
                                        (
                                            "ERROR",
                                            f"{os.path.basename(file_path)} line {row_idx}: Value '{value}' for '{col_name}' is not numeric but has numeric constraints",
                                        )
                                    )

                if row_count == 0:
                    issues.append(
                        (
                            "WARNING",
                            f"File {os.path.basename(file_path)} contains no data rows. If data is missing, please delete the file.",
                        )
                    )

        except Exception as e:
            issues.append(
                (
                    "ERROR",
                    f"Error validating content of {os.path.basename(file_path)}: {str(e)}",
                )
            )

        return issues

    def validate_filename(self, filename, modality, subject_id=None, session_id=None):
        """Validate filename against BIDS conventions and modality patterns"""
        issues = []

        # Cross-platform filename validation
        platform_issues = validate_filename_cross_platform(filename)
        for issue in platform_issues:
            issues.append(("WARNING", issue))

        base, ext = split_compound_ext(filename)
        pattern = re.compile(MODALITY_PATTERNS.get(modality, r".*"))
        is_sidecar = filename.endswith(".json")

        # Check BIDS naming
        if not BIDS_REGEX.match(base):
            issues.append(("ERROR", f"Invalid BIDS filename format: {filename}"))

        # Check modality pattern
        if not is_sidecar and not pattern.match(filename):
            issues.append(
                (
                    "WARNING",
                    f"Filename doesn't match expected pattern for {modality}: {filename}",
                )
            )

        # Check MRI-specific patterns
        if modality in ("anat", "func", "fmap", "dwi"):
            if ext in (".nii", ".nii.gz") and not MRI_SUFFIX_REGEX.search(base):
                issues.append(
                    ("ERROR", f"Invalid MRI suffix for {modality}: {filename}")
                )

        # Check subject consistency
        if subject_id:
            if not filename.startswith(subject_id + "_"):
                issues.append(
                    (
                        "ERROR",
                        f"Filename {filename} does not start with subject ID {subject_id}",
                    )
                )

        # Check session consistency
        if session_id:
            # Expecting sub-XX_ses-YY_...
            expected_prefix = f"{subject_id}_{session_id}_"
            if not filename.startswith(expected_prefix):
                issues.append(
                    (
                        "ERROR",
                        f"Filename {filename} does not match session directory {session_id}",
                    )
                )
        elif subject_id:
            # If no session directory, filename should not contain session entity
            # But we need to be careful not to match "ses-" if it appears elsewhere (unlikely in BIDS but possible)
            # BIDS session entity is always "_ses-<label>"
            if "_ses-" in filename:
                issues.append(
                    (
                        "ERROR",
                        f"Filename {filename} contains session entity but is not in a session directory",
                    )
                )

        return issues

    def validate_sidecar(self, file_path, modality, root_dir):
        """Validate JSON sidecar against schema"""
        sidecar_path = resolve_sidecar_path(file_path, root_dir)
        issues = []

        if not os.path.exists(sidecar_path):
            return [("ERROR", f"Missing sidecar for {normalize_path(file_path)}")]

        try:
            # Use cross-platform file reading
            content = CrossPlatformFile.read_text(sidecar_path)
            sidecar_data = json.loads(content)

            # Validate against schema if available
            schema = self.schemas.get(modality)
            if schema:
                # Version compatibility checks (only warns when explicitly specified and incompatible)
                issues.extend(validate_schema_version(sidecar_data, schema))
                validate(instance=sidecar_data, schema=schema)

        except ValidationError as e:
            issues.append(
                ("ERROR", f"{normalize_path(sidecar_path)} schema error: {e.message}")
            )
        except json.JSONDecodeError as e:
            issues.append(
                ("ERROR", f"{normalize_path(sidecar_path)} is not valid JSON: {e}")
            )
        except Exception as e:
            issues.append(
                ("ERROR", f"Error processing {normalize_path(sidecar_path)}: {e}")
            )

        return issues
