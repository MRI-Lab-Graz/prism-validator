# Error Codes Reference

This document describes all validation error codes used by Prism-Validator and how to fix them.

## Table of Contents

- [INVALID_BIDS_FILENAME](#invalid_bids_filename)
- [MISSING_SIDECAR](#missing_sidecar)
- [SCHEMA_VALIDATION_ERROR](#schema_validation_error)
- [INVALID_JSON](#invalid_json)
- [FILENAME_PATTERN_MISMATCH](#filename_pattern_mismatch)

---

## INVALID_BIDS_FILENAME

**Description:** Filenames must follow BIDS naming convention (sub-\<label\>_[ses-\<label\>_]...)

**Common Causes:**
- Missing required `sub-` prefix
- Invalid characters in labels (only alphanumeric allowed)
- Missing required entities for certain modalities
- Incorrect ordering of BIDS entities

**How to Fix:**

BIDS filenames follow this pattern:
```
sub-<label>_[ses-<label>_][task-<label>_][run-<index>_]<suffix>.<extension>
```

**Examples of Valid Filenames:**
- `sub-01_task-faces_bold.nii.gz`
- `sub-01_ses-01_task-nback_eeg.edf`
- `sub-02_task-rest_physio.tsv`
- `sub-01_T1w.nii.gz`

**Examples of Invalid Filenames:**
- `subject01_task-faces.nii.gz` ❌ (missing `sub-` prefix)
- `sub-01-task-faces.nii.gz` ❌ (use `_` not `-` between entities)
- `task-recognition_stim.json` ❌ (missing `sub-` prefix)
- `dataset_description.json` ❌ (root-level files don't follow BIDS naming - this is a special case that should be at dataset root)

**Resources:**
- [BIDS Specification: Common Principles](https://bids-specification.readthedocs.io/en/stable/02-common-principles.html#file-name-structure)
- [BIDS Specification: Entity Key Table](https://bids-specification.readthedocs.io/en/stable/99-appendices/04-entity-table.html)

---

## MISSING_SIDECAR

**Description:** Required JSON sidecar files are missing for data files

**Common Causes:**
- JSON sidecar file was not created for a data file
- JSON sidecar has different base name than the data file
- JSON sidecar is in a different directory

**How to Fix:**

Each data file needs a corresponding JSON sidecar with metadata. The JSON file should have the same base name as the data file but with `.json` extension.

**Example:**
```
sub-01/
  ses-01/
    func/
      sub-01_ses-01_task-nback_bold.nii.gz     # Data file
      sub-01_ses-01_task-nback_bold.json       # Required sidecar
```

**Minimum Required Fields** (vary by modality):
```json
{
  "TaskName": "N-back working memory",
  "SamplingFrequency": 1000,
  "TaskDescription": "Participants view stimuli..."
}
```

**Resources:**
- [BIDS Specification: Metadata Files](https://bids-specification.readthedocs.io/en/stable/02-common-principles.html#metadata-files)

---

## SCHEMA_VALIDATION_ERROR

**Description:** JSON sidecar content does not match required schema

**Common Causes:**
- Required fields are missing
- Field values have incorrect type (e.g., string instead of number)
- Field values are outside valid range
- Extra fields that are not allowed

**How to Fix:**

Check the schema requirements for your modality:
- `schemas/eeg.schema.json` for EEG data
- `schemas/eyetracking.schema.json` for eye-tracking data
- `schemas/physiological.schema.json` for physiological recordings
- etc.

**Example Error:**
```
"SamplingFrequency" is required but missing
```

**Fix:**
```json
{
  "SamplingFrequency": 1000,
  "TaskName": "rest"
}
```

**Common Required Fields by Modality:**

**EEG:**
- `SamplingFrequency` (number, Hz)
- `EEGReference` (string)
- `PowerLineFrequency` (number, 50 or 60)

**Eye-tracking:**
- `SamplingFrequency` (number, Hz)
- `ScreenResolution` (array of 2 numbers)
- `EyeTrackingSoftware` (string)

**Physiological:**
- `SamplingFrequency` (number, Hz)
- `Columns` (array of strings)

**Resources:**
- [Schema Versioning Guide](SCHEMA_VERSIONING_GUIDE.md)
- Check `schemas/` directory for complete requirements

---

## INVALID_JSON

**Description:** JSON files contain syntax errors or are not valid JSON

**Common Causes:**
- Missing quotes around strings
- Missing commas between fields
- Trailing commas after last field
- Using single quotes instead of double quotes
- Unescaped special characters
- Invalid UTF-8 encoding

**How to Fix:**

**Invalid JSON:**
```text
{
  "TaskName": 'faces',    # Single quotes - invalid!
  "Duration": 300,        # Trailing comma - invalid!
}
```

**Valid JSON:**
```json
{
  "TaskName": "faces",
  "Duration": 300
}
```

**Validation Tools:**
- Use `jsonlint` or online JSON validators
- Most code editors have JSON validation built-in
- Python: `python -m json.tool your_file.json`

**Resources:**
- [JSON Specification](https://www.json.org/)
- [JSONLint Online Validator](https://jsonlint.com/)

---

## FILENAME_PATTERN_MISMATCH

**Description:** Filenames do not match expected patterns for their modality

**Common Causes:**
- Wrong file extension for modality
- Missing required suffix
- File is in wrong modality directory

**How to Fix:**

Each modality expects specific file extensions and suffixes:

**Movie/Video:**
- Extension: `.mp4`
- Directory: `movie/`

**Images:**
- Extensions: `.png`, `.jpg`, `.jpeg`, `.tiff`
- Directory: `image/`

**EEG:**
- Extensions: `.edf`, `.bdf`, `.eeg`
- Directory: `eeg/`

**Eye-tracking:**
- Extensions: `.tsv`, `.edf`
- Directory: `eyetracking/`

**Behavioral:**
- Extension: `.tsv`
- Directory: `behavior/`

**MRI (Anatomical):**
- Extension: `.nii` or `.nii.gz`
- Required suffix: `_T1w`, `_T2w`, `_FLAIR`, etc.
- Directory: `anat/`

**MRI (Functional):**
- Extension: `.nii` or `.nii.gz`
- Required suffix: `_bold`
- Directory: `func/`

**Example Error:**
```
sub-01_task-faces_bold.mp4 in func/ directory
```

**Fix:** Either:
1. Change extension to `.nii.gz` if it's actually fMRI data
2. Move to `movie/` directory and rename to valid movie filename

**Resources:**
- [BIDS Specification: Modality Specific Files](https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html)

---

## Getting Help

If you're still stuck after reading this documentation:

1. Check [USAGE.md](USAGE.md) for general guidance
2. Review example datasets in `docs/examples/`
3. Open an issue on [GitHub](https://github.com/MRI-Lab-Graz/prism-validator/issues)
4. Consult the [BIDS Specification](https://bids-specification.readthedocs.io/)

## Quick Fixes Checklist

- [ ] All filenames start with `sub-<label>_`
- [ ] Entities are separated by `_` not `-`
- [ ] File extensions match modality (`.nii.gz` for MRI, `.edf` for EEG, etc.)
- [ ] JSON sidecar exists for every data file
- [ ] JSON files are valid (no syntax errors)
- [ ] JSON sidecars contain all required fields for the modality
- [ ] Files are in correct modality directories
- [ ] `dataset_description.json` exists at dataset root
