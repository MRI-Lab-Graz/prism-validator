import pandas as pd
import json
import os
import sys
import argparse


def load_schemas(library_path):
    """Load all survey JSONs from the library."""
    schemas = {}
    if not os.path.exists(library_path):
        print(f"Warning: Library path {library_path} does not exist.")
        return schemas

    for f in os.listdir(library_path):
        if f.endswith(".json") and f.startswith("survey-"):
            # Extract task name: survey-ads.json -> ads
            task_name = f.replace("survey-", "").replace(".json", "")
            with open(os.path.join(library_path, f), "r") as jf:
                try:
                    schemas[task_name] = json.load(jf)
                except json.JSONDecodeError:
                    print(f"Error decoding {f}, skipping.")
    return schemas


IGNORE_PARTICIPANT_COLS = {
    "submitdate",
    "lastpage",
    "startlanguage",
    "seed",
    "startdate",
    "datestamp",
    "token",
    "language",
}


def _allowed_values(col_def):
    """Return allowed values for a column, expanding numeric level endpoints to full range."""
    if not isinstance(col_def, dict):
        return None

    if "AllowedValues" in col_def:
        return [str(x) for x in col_def["AllowedValues"]]

    if "Levels" in col_def:
        level_keys = list(col_def["Levels"].keys())
        try:
            numeric_levels = [int(float(k)) for k in level_keys]
        except ValueError:
            numeric_levels = []

        if numeric_levels:
            min_level = min(numeric_levels)
            max_level = max(numeric_levels)
            full_range = [str(i) for i in range(min_level, max_level + 1)]
            if set(full_range).issuperset(set(level_keys)):
                return full_range
        return level_keys

    return None


def _ensure_participants(df, id_col, output_root, library_path, candidates=None, participant_schema=None):
    """Create participants.tsv/json. Prefer explicit participant schema or library participants.json; otherwise infer."""
    rawdata_dir = os.path.join(output_root, "rawdata")
    os.makedirs(rawdata_dir, exist_ok=True)

    participants_json_path = os.path.join(library_path, "participants.json")
    inferred = False
    used_schema = False

    if participant_schema:
        part_schema = participant_schema
        used_schema = True
    elif not os.path.exists(participants_json_path):
        # Build a minimal schema from candidates
        cols = candidates or []
        cols = [c for c in cols if c != id_col]
        if not cols:
            return
        part_schema = {
            "participant_id": {
                "Description": "Participant identifier (sub-<label>)"
            }
        }
        for col in cols:
            part_schema[col] = {"Description": f"Participant attribute '{col}'"}
        inferred = True
    else:
        with open(participants_json_path, "r") as f:
            part_schema = json.load(f)

    print("Generating participants.tsv using participant schema..." if (used_schema or not inferred) else "Generating inferred participants.tsv...")
    try:
        part_vars = [k for k in part_schema.keys() if k not in ["Technical", "Study", "Metadata"]]
        found_part_vars = [v for v in part_vars if v in df.columns]
        
        # Ensure id_col is not in found_part_vars to avoid "cannot insert... already exists" during reset_index
        if id_col in found_part_vars:
            found_part_vars.remove(id_col)

        if found_part_vars:
            df_part = df.groupby(id_col)[found_part_vars].first().reset_index()
            df_part = df_part.rename(columns={id_col: "participant_id"})
            df_part["participant_id"] = df_part["participant_id"].apply(
                lambda x: f"sub-{x}" if not str(x).startswith("sub-") else str(x)
            )

            # Clean values against allowed values; fallback to 'n/a' when out of range/enum
            for col in found_part_vars:
                col_def = part_schema.get(col, {})
                allowed = _allowed_values(col_def)
                if allowed:
                    df_part[col] = df_part[col].apply(
                        lambda v: v if pd.isna(v) or str(v) in allowed else "n/a"
                    )

            part_tsv_path = os.path.join(rawdata_dir, "participants.tsv")
            df_part.to_csv(part_tsv_path, sep="\t", index=False)
            print(
                f"  - Created participants.tsv with {len(df_part)} subjects and {len(found_part_vars)} columns."
            )

            with open(os.path.join(rawdata_dir, "participants.json"), "w") as f:
                json.dump(part_schema, f, indent=2)
        else:
            if inferred:
                print("  - No participant columns found to infer participants.tsv.")
            else:
                print("  - participants.json found but no matching columns in data.")
    except Exception as e:
        print(f"Error processing participants.tsv: {e}")


def process_data(csv_file, schemas, output_root, library_path):
    """Convert CSV data to BIDS TSV files based on JSON schemas."""
    print(f"Loading data from {csv_file}...")
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    process_dataframe(df, schemas, output_root, library_path)


def process_dataframe(df, schemas, output_root, library_path, session_override=None, run_override=None):
    """Convert in-memory dataframe to BIDS TSV files based on JSON schemas."""
    rawdata_dir = os.path.join(output_root, "rawdata")
    os.makedirs(rawdata_dir, exist_ok=True)

    id_cols = [
        c
        for c in df.columns
        if c.lower() in ["participant_id", "subject", "id", "sub_id", "participant"]
    ]
    if not id_cols:
        first_col = df.columns[0]
        if "id" in first_col.lower() or "sub" in first_col.lower():
            id_cols = [first_col]
        else:
            print("Error: Could not find a participant ID column (e.g., 'participant_id', 'subject').")
            return
    id_col = id_cols[0]
    print(f"Using '{id_col}' as participant ID column.")

    # Identify all schema variables to separate participant-only columns when no participants.json
    all_schema_vars = set()
    for schema in schemas.values():
        for k in schema.keys():
            if k in ["Technical", "Study", "Metadata"]:
                continue
            all_schema_vars.add(k)

    candidate_participant_cols = []
    for col in df.columns:
        lc = col.lower()
        if col == id_col:
            continue
        if col in all_schema_vars:
            continue
        if lc in IGNORE_PARTICIPANT_COLS or lc.startswith("_"):
            continue
        candidate_participant_cols.append(col)

    _ensure_participants(
        df,
        id_col,
        output_root,
        library_path,
        candidates=candidate_participant_cols,
        participant_schema=schemas.get("participant"),
    )

    # Iterate over each defined survey schema
    for task_name, schema in schemas.items():
        print(f"Processing survey: {task_name}...")

        # Skip per-subject participant task files; participants handled at dataset root.
        if task_name == "participant":
            print("  - Skipping per-subject participants; handled via participants.tsv/json at dataset root.")
            continue

        # 1. Identify variables belonging to this survey
        # Exclude standard metadata sections
        survey_vars = [
            k for k in schema.keys() if k not in ["Technical", "Study", "Metadata"]
        ]

        # Build canonical mapping and hints
        canonical_for = {}
        session_hint = {}
        run_hint = {}
        canonical_order = []

        for var in survey_vars:
            alias_of = schema.get(var, {}).get("AliasOf")
            canon = alias_of if alias_of else var
            canonical_for[var] = canon
            if canon not in canonical_order:
                canonical_order.append(canon)
            if "SessionHint" in schema.get(var, {}):
                session_hint[var] = schema[var]["SessionHint"]
            if "RunHint" in schema.get(var, {}):
                run_hint[var] = schema[var]["RunHint"]

        # Map per-variable session hints if present
        var_session_hint = {}
        for var in survey_vars:
            hint = schema.get(var, {}).get("SessionHint")
            if hint:
                var_session_hint[var] = hint

        # 2. Find which of these variables exist in the CSV
        # We check for exact match, but you could add case-insensitive logic here
        found_vars = [v for v in survey_vars if v in df.columns]

        if not found_vars:
            print(
                f"  - No data found for {task_name} (checked {len(survey_vars)} variables). Skipping."
            )
            continue

        print(f"  - Found {len(found_vars)} variables for {task_name}.")

        # 3. Create TSV for each participant, respecting per-variable session/run hints
        for _, row in df.iterrows():
            sub_id = str(row[id_col])

            # Normalize subject ID (ensure sub- prefix)
            if not sub_id.startswith("sub-"):
                sub_id = f"sub-{sub_id}"

            # Default session/run from row (if present) or fallback
            base_ses = session_override or "ses-1"
            if "session" in df.columns:
                ses_val = str(row["session"])
                base_ses = f"ses-{ses_val}" if not ses_val.startswith("ses-") else ses_val

            base_run = run_override or "run-1"
            if "run" in df.columns:
                run_val = str(row["run"])
                base_run = f"run-{run_val}" if not run_val.startswith("run-") else run_val

            # Partition variables by session
            buckets = {}
            for var in found_vars:
                ses = var_session_hint.get(var, session_hint.get(var, base_ses))
                run = run_hint.get(var, base_run)
                buckets.setdefault((ses, run), []).append(var)

            for (ses_id, run_id), vars_in_bucket in buckets.items():
                out_dir = os.path.join(rawdata_dir, sub_id, ses_id, "survey")
                os.makedirs(out_dir, exist_ok=True)

                row_data = row[vars_in_bucket].to_dict()

                # Map to canonical keys and prefer first non-NaN if duplicates appear
                merged = {}
                for var, val in row_data.items():
                    canon = canonical_for.get(var, var)
                    if canon not in merged or (pd.isna(merged[canon]) and pd.notna(val)):
                        merged[canon] = val

                # Ensure columns follow canonical order
                ordered_keys = [k for k in canonical_order if k in merged]
                clean_data = {}
                for k in ordered_keys:
                    val = merged[k]
                    if pd.isna(val):
                        clean_data[k] = "n/a"
                        continue

                    col_def = schema.get(k, {})
                    allowed = _allowed_values(col_def)
                    if allowed and str(val) not in allowed:
                        clean_data[k] = "n/a"
                    else:
                        clean_data[k] = val

                df_task = pd.DataFrame([clean_data])

                run_suffix = ""
                if run_id and run_id != "run-1":
                    part = run_id.split("-", 1)[1] if "-" in run_id else run_id
                    run_suffix = f"_run-{part}"
                tsv_name = f"{sub_id}_{ses_id}_task-{task_name}{run_suffix}_beh.tsv"
                tsv_path = os.path.join(out_dir, tsv_name)

                df_task.to_csv(tsv_path, sep="\t", index=False)

        # 4. Ensure JSON sidecars exist in the root (BIDS inheritance)
        # Keep legacy survey-<task>.json and also emit task-<task>_beh.json for stricter BIDS tools.
        legacy_name = f"survey-{task_name}.json"
        legacy_path = os.path.join(rawdata_dir, legacy_name)
        bids_name = f"task-{task_name}_beh.json"
        bids_path = os.path.join(rawdata_dir, bids_name)

        for path in (legacy_path, bids_path):
            if not os.path.exists(path):
                with open(path, "w") as f:
                    json.dump(schema, f, indent=2)

    print("Conversion complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert CSV data to BIDS TSVs using JSON schemas."
    )
    parser.add_argument("--csv", required=True, help="Path to the large CSV data file.")
    parser.add_argument(
        "--library",
        default="survey_library",
        help="Path to the folder containing survey-*.json files.",
    )
    parser.add_argument(
        "--output", default="PK01", help="Root directory of the dataset."
    )

    args = parser.parse_args()

    schemas = load_schemas(args.library)
    if not schemas:
        print("No schemas found. Exiting.")
        sys.exit(1)

    process_data(args.csv, schemas, args.output, args.library)
