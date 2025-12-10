#!/usr/bin/env python3
import argparse
import sys
import os
import shutil
from pathlib import Path
import glob

# Add project root to path to import helpers
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from helpers.physio.convert_varioport import convert_varioport
from scripts.check_survey_library import check_uniqueness
from scripts.limesurvey_to_prism import convert_lsa_to_prism, batch_convert_lsa
# excel_to_library might not be in python path if it's in scripts/ and we are in root.
# sys.path.append(str(project_root / "scripts")) # Already added project_root, but scripts is a subdir.
# We need to import from scripts.excel_to_library
from scripts.excel_to_library import process_excel

def sanitize_id(id_str):
    """
    Sanitizes subject/session IDs by replacing German umlauts and special characters.
    """
    if not id_str:
        return id_str
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'ß': 'ss'
    }
    for char, repl in replacements.items():
        id_str = id_str.replace(char, repl)
    return id_str

import json
import hashlib

def get_json_hash(json_path):
    """Calculates hash of a JSON file's content."""
    with open(json_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def consolidate_sidecars(output_dir, task, suffix):
    """
    Consolidates identical JSON sidecars into a single file in the root directory.
    """
    print("\nConsolidating JSON sidecars...")
    # Find all generated JSONs for this task/suffix
    # Pattern: sub-*/ses-*/physio/*_task-<task>_<suffix>.json
    pattern = f"sub-*/ses-*/physio/*_task-{task}_{suffix}.json"
    json_files = list(output_dir.glob(pattern))
    
    if not json_files:
        print("No sidecars found to consolidate.")
        return

    first_json = json_files[0]
    first_hash = get_json_hash(first_json)
    
    all_identical = True
    for jf in json_files[1:]:
        if get_json_hash(jf) != first_hash:
            all_identical = False
            break
    
    if all_identical:
        print(f"All {len(json_files)} sidecars are identical. Consolidating to root.")
        # Create root sidecar name: task-<task>_<suffix>.json
        root_json_name = f"task-{task}_{suffix}.json"
        root_json_path = output_dir / root_json_name
        
        # Copy first json to root
        shutil.copy(first_json, root_json_path)
        print(f"Created root sidecar: {root_json_path}")
        
        # Delete individual sidecars
        for jf in json_files:
            jf.unlink()
        print("Deleted individual sidecars.")
    else:
        print("Sidecars differ. Keeping individual files.")

def cmd_convert_physio(args):
    """
    Handles the 'convert physio' command.
    """
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist.")
        sys.exit(1)

    print(f"Scanning {input_dir} for raw physio files...")
    
    # Expected structure: sourcedata/sub-XXX/ses-YYY/physio/filename.raw
    # We search recursively for the raw files
    # The pattern should be flexible but ideally match the BIDS-like structure
    
    # Find all files matching the pattern
    # We assume files end with .raw or .RAW (case insensitive check later if needed)
    # But glob is case sensitive on Linux.
    files = list(input_dir.rglob("*.[rR][aA][wW]"))
    
    if not files:
        print("No .raw files found in input directory.")
        return

    print(f"Found {len(files)} files to process.")
    
    success_count = 0
    error_count = 0
    
    for raw_file in files:
        # Infer subject and session from path or filename
        # Expected filename: sub-<id>_ses-<id>_physio.raw
        filename = raw_file.name
        
        # Simple parsing logic
        parts = raw_file.stem.split('_')
        sub_id = None
        ses_id = None
        
        for part in parts:
            if part.startswith('sub-'):
                sub_id = part
            elif part.startswith('ses-'):
                ses_id = part
        
        # Fallback: try to get from parent folders if not in filename
        if not sub_id:
            for parent in raw_file.parents:
                if parent.name.startswith('sub-'):
                    sub_id = parent.name
                    break
        
        if not ses_id:
            for parent in raw_file.parents:
                if parent.name.startswith('ses-'):
                    ses_id = parent.name
                    break
        
        if not sub_id or not ses_id:
            print(f"Skipping {filename}: Could not determine subject or session ID.")
            continue
        
        # Sanitize IDs
        sub_id = sanitize_id(sub_id)
        ses_id = sanitize_id(ses_id)
            
        # Construct output path
        # rawdata/sub-XXX/ses-YYY/physio/
        target_dir = output_dir / sub_id / ses_id / "physio"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Construct output filename
        # sub-XXX_ses-YYY_task-<task>_<suffix>.edf
        out_base = f"{sub_id}_{ses_id}_task-{args.task}_{args.suffix}"
        out_edf = target_dir / f"{out_base}.edf"
        out_json = target_dir / f"{out_base}.json"
        
        print(f"Converting {filename} -> {out_base}.edf")
        
        try:
            convert_varioport(
                str(raw_file),
                str(out_edf),
                str(out_json),
                task_name=args.task,
                base_freq=args.sampling_rate
            )
            
            # Check file size
            if out_edf.exists():
                size_kb = out_edf.stat().st_size / 1024
                if size_kb < 10: # Warn if smaller than 10KB
                    print(f"⚠️  WARNING: Output file is suspiciously small ({size_kb:.2f} KB): {out_edf}")
                else:
                    print(f"✅ Created {out_edf.name} ({size_kb:.2f} KB)")
            else:
                 print(f"❌ Error: Output file was not created: {out_edf}")
                 error_count += 1
                 continue

            success_count += 1
        except Exception as e:
            print(f"Error converting {filename}: {e}")
            error_count += 1
            
    # Consolidate sidecars if requested (or always?)
    # BIDS inheritance principle
    consolidate_sidecars(output_dir, args.task, args.suffix)

    print(f"\nConversion finished. Success: {success_count}, Errors: {error_count}")

def cmd_demo_create(args):
    """
    Creates a demo dataset.
    """
    output_path = Path(args.output)
    demo_source = project_root / "prism_demo"
    
    if output_path.exists():
        print(f"Error: Output path '{output_path}' already exists.")
        sys.exit(1)
        
    print(f"Creating demo dataset at {output_path}...")
    try:
        shutil.copytree(demo_source, output_path)
        print("✅ Demo dataset created successfully.")
    except Exception as e:
        print(f"Error creating demo dataset: {e}")
        sys.exit(1)

def cmd_survey_import_excel(args):
    """
    Imports survey library from Excel.
    """
    print(f"Importing survey library from {args.excel}...")
    try:
        process_excel(args.excel, args.output)
    except Exception as e:
        print(f"Error importing Excel: {e}")
        sys.exit(1)

def cmd_survey_validate(args):
    """
    Validates the survey library.
    """
    print(f"Validating survey library at {args.library}...")
    if check_uniqueness(args.library):
        sys.exit(0)
    else:
        sys.exit(1)

def cmd_survey_import_limesurvey(args):
    """
    Imports LimeSurvey structure.
    """
    print(f"Importing LimeSurvey structure from {args.input}...")
    try:
        convert_lsa_to_prism(args.input, args.output, task_name=args.task)
    except Exception as e:
        print(f"Error importing LimeSurvey: {e}")
        sys.exit(1)


def parse_session_map(map_str):
    mapping = {}
    for item in map_str.split(','):
        token = item.strip()
        if not token:
            continue
        sep = ':' if ':' in token else ('=' if '=' in token else None)
        if not sep:
            # allow shorthand like t1_ses-1
            if '_' in token:
                raw, mapped = token.split('_', 1)
            else:
                continue
        else:
            raw, mapped = token.split(sep, 1)
        mapping[raw.strip().lower()] = mapped.strip()
    return mapping


def cmd_survey_import_limesurvey_batch(args):
    """Batch convert LimeSurvey archives with session mapping (t1/t2/t3 -> ses-1/2/3)."""
    session_map = parse_session_map(args.session_map)
    if not session_map:
        print("No valid session mapping provided. Example: t1:ses-1,t2:ses-2,t3:ses-3")
        sys.exit(1)
    try:
        batch_convert_lsa(
            args.input_dir,
            args.output_dir,
            session_map,
            library_path=args.library,
            task_fallback=args.task,
            id_column=args.subject_id_col,
            id_map_file=args.id_map,
        )
    except Exception as e:
        print(f"Error importing LimeSurvey: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Prism Tools: Utilities for PRISM/BIDS datasets")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Command: convert
    parser_convert = subparsers.add_parser("convert", help="Convert raw data to BIDS format")
    convert_subparsers = parser_convert.add_subparsers(dest="modality", help="Modality to convert")
    
    # Subcommand: convert physio
    parser_physio = convert_subparsers.add_parser("physio", help="Convert physiological data (Varioport)")
    parser_physio.add_argument("--input", required=True, help="Path to sourcedata directory")
    parser_physio.add_argument("--output", required=True, help="Path to output rawdata directory")
    parser_physio.add_argument("--task", default="rest", help="Task name (default: rest)")
    parser_physio.add_argument("--suffix", default="physio", help="Output suffix (default: physio)")
    parser_physio.add_argument("--sampling-rate", type=float, help="Override sampling rate (e.g. 256)")
    
    # Command: demo
    parser_demo = subparsers.add_parser("demo", help="Demo dataset operations")
    demo_subparsers = parser_demo.add_subparsers(dest="action", help="Action")
    
    # Subcommand: demo create
    parser_demo_create = demo_subparsers.add_parser("create", help="Create a demo dataset")
    parser_demo_create.add_argument("--output", default="prism_demo_copy", help="Output path for the demo dataset")

    # Command: survey
    parser_survey = subparsers.add_parser("survey", help="Survey library operations")
    survey_subparsers = parser_survey.add_subparsers(dest="action", help="Action")
    
    # Subcommand: survey import-excel
    parser_survey_excel = survey_subparsers.add_parser("import-excel", help="Import survey library from Excel")
    parser_survey_excel.add_argument("--excel", required=True, help="Path to Excel file")
    parser_survey_excel.add_argument("--output", default="survey_library", help="Output directory")
    
    # Subcommand: survey validate
    parser_survey_validate = survey_subparsers.add_parser("validate", help="Validate survey library")
    parser_survey_validate.add_argument("--library", default="survey_library", help="Path to survey library")
    
    # Subcommand: survey import-limesurvey
    parser_survey_limesurvey = survey_subparsers.add_parser("import-limesurvey", help="Import LimeSurvey structure")
    parser_survey_limesurvey.add_argument("--input", required=True, help="Path to .lsa/.lss file")
    parser_survey_limesurvey.add_argument("--output", help="Path to output .json file")
    parser_survey_limesurvey.add_argument("--task", help="Optional task name override (defaults from file name)")

    parser_survey_limesurvey_batch = survey_subparsers.add_parser(
        "import-limesurvey-batch", help="Batch import LimeSurvey files with session mapping"
    )
    parser_survey_limesurvey_batch.add_argument("--input-dir", required=True, help="Root directory containing .lsa/.lss files")
    parser_survey_limesurvey_batch.add_argument("--output-dir", required=True, help="Output root for generated PRISM dataset")
    parser_survey_limesurvey_batch.add_argument(
        "--session-map",
        default="t1:ses-1,t2:ses-2,t3:ses-3",
        help="Comma-separated mapping, e.g. t1:ses-1,t2:ses-2,t3:ses-3",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--task",
        help="Optional task name fallback (otherwise derived from file name)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--library",
        default="survey_library",
        help="Path to survey library (survey-*.json and optional participants.json)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--subject-id-col",
        dest="subject_id_col",
        help="Preferred column name to use for participant ID (e.g., ID, code, token)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--id-map",
        dest="id_map",
        help="Path to TSV/CSV file mapping LimeSurvey IDs to BIDS participant IDs (cols: limesurvey_id, participant_id)",
    )

    args = parser.parse_args()
    
    if args.command == "convert" and args.modality == "physio":
        cmd_convert_physio(args)
    elif args.command == "demo" and args.action == "create":
        cmd_demo_create(args)
    elif args.command == "survey":
        if args.action == "import-excel":
            cmd_survey_import_excel(args)
        elif args.action == "validate":
            cmd_survey_validate(args)
        elif args.action == "import-limesurvey":
            cmd_survey_import_limesurvey(args)
        elif args.action == "import-limesurvey-batch":
            cmd_survey_import_limesurvey_batch(args)
        else:
            parser_survey.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
