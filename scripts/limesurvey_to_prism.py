import argparse
import json
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd

from scripts.csv_to_prism import load_schemas, process_dataframe

def sanitize_task_name(name):
    """Normalize task names for BIDS/PRISM filenames."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", name.strip()).strip("-")
    return cleaned.lower() or "survey"


def _map_field_to_code(fieldname, qid_to_title):
    m = re.match(r"(\d+)X(\d+)X(\d+)([A-Za-z0-9_]+)?", fieldname)
    if not m:
        return fieldname
    qid = m.group(3)
    suffix = m.group(4)
    if suffix:
        return suffix
    return qid_to_title.get(qid, fieldname)


def parse_lsa_responses(lsa_path):
    """Return (dataframe, qid->title mapping, groups_map) extracted from a LimeSurvey .lsa file."""
    with zipfile.ZipFile(lsa_path, "r") as z:
        xml_resp = z.read(next(n for n in z.namelist() if n.endswith("_responses.lsr")))
        xml_lss = z.read(next(n for n in z.namelist() if n.endswith(".lss")))

    lss_root = ET.fromstring(xml_lss)
    
    # Helper to find text of a child element
    def get_text(element, tag):
        child = element.find(tag)
        val = child.text if child is not None else ""
        return val or ""

    questions_map, groups_map = _parse_lss_structure(lss_root, get_text)
    
    # Build simple qid->title map for column renaming
    qid_to_title = {qid: d['title'] for qid, d in questions_map.items()}
    
    # Also include subquestions in qid_to_title if needed?
    # The original code did this:
    for row in lss_root.findall(".//subquestions/rows/row"):
        qid = row.find("qid").text
        title = row.find("title").text
        qid_to_title[qid] = title

    text = xml_resp.decode("utf-8")
    fieldnames = re.findall(r"<fieldname>(.*?)</fieldname>", text)

    # Parse rows by XML to preserve order and decode CDATA
    resp_root = ET.fromstring(xml_resp)
    rows = resp_root.findall("./responses/rows/row")
    records = []
    for row in rows:
        rec = {}
        for child in row:
            tag = child.tag.lstrip("_")
            rec[tag] = child.text
        records.append(rec)

    df = pd.DataFrame(records)

    rename_map = {f: _map_field_to_code(f, qid_to_title) for f in fieldnames}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    return df, questions_map, groups_map


def parse_lsa_timings(lsa_path):
    """Extract and parse the _timings.lsi file from a .lsa archive."""
    if not os.path.exists(lsa_path):
        return None

    try:
        with zipfile.ZipFile(lsa_path, 'r') as zf:
            timings_files = [f for f in zf.namelist() if f.endswith('_timings.lsi')]
            if not timings_files:
                return None
            
            with zf.open(timings_files[0]) as f:
                xml_content = f.read()
                
        root = ET.fromstring(xml_content)
        rows = root.findall(".//row")
        if not rows:
            return None
            
        records = []
        for row in rows:
            rec = {}
            for child in row:
                # Tag is like _244841X43550time
                tag = child.tag
                val = child.text
                rec[tag] = val
            records.append(rec)
            
        try:
            return pd.DataFrame(records)
        except Exception as e:
            print(f"Error creating DataFrame in parse_lsa_timings: {e}")
            return None
    except Exception as e:
        print(f"Warning: Failed to parse timings from {lsa_path}: {e}")
        return None



def _parse_lss_structure(root, get_text):
    # 1. Parse Questions
    # Map qid -> {title, question, type, ...}
    questions_map = {}
    # Map gid -> title string (Group info)
    groups_map = {}
    
    # Find the <groups> section to map Group ID -> Group Name (if available)
    groups_section = root.find('groups')
    if groups_section is not None:
        rows = groups_section.find('rows')
        if rows is not None:
            for row in rows.findall('row'):
                gid = get_text(row, 'gid')
                name = get_text(row, 'group_name')
                groups_map[gid] = name if name else ""

    # Find the <questions> section
    questions_section = root.find('questions')
    if questions_section is not None:
        rows = questions_section.find('rows')
        if rows is not None:
            for row in rows.findall('row'):
                qid = get_text(row, 'qid')
                gid = get_text(row, 'gid')
                title = get_text(row, 'title') # This is usually the variable name (e.g. 'age', 'gender')
                question_text = get_text(row, 'question')
                q_type = get_text(row, 'type')
                parent_qid = get_text(row, 'parent_qid')
                
                # Clean up CDATA or HTML tags from question text if necessary
                clean_question = re.sub('<[^<]+?>', '', question_text or '').strip()
                
                questions_map[qid] = {
                    'title': title,
                    'question': clean_question,
                    'type': q_type,
                    'parent_qid': parent_qid,
                    'gid': gid,
                    'levels': {}
                }
                
                # Update group map with a representative title if not set
                if gid in groups_map and not groups_map[gid]:
                    # Heuristic: use the first question's variable name prefix?
                    # Or just the variable name.
                    # If we have ADS01, ADS02, usually the group is ADS.
                    # Let's try to strip digits.
                    prefix = re.match(r"([a-zA-Z]+)", title)
                    if prefix:
                        groups_map[gid] = prefix.group(1)
                    else:
                        groups_map[gid] = title

    return questions_map, groups_map

def parse_lss_xml(xml_content, task_name=None):
    """Parse a LimeSurvey .lss XML blob into a Prism sidecar dict."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None

    # Helper to find text of a child element
    def get_text(element, tag):
        child = element.find(tag)
        val = child.text if child is not None else ""
        return val or ""

    questions_map, groups_map = _parse_lss_structure(root, get_text)

    # 2. Parse Answers
    # Map qid -> {code: answer, ...}
    answers_section = root.find('answers')
    if answers_section is not None:
        rows = answers_section.find('rows')
        if rows is not None:
            for row in rows.findall('row'):
                qid = get_text(row, 'qid')
                code = get_text(row, 'code')
                answer = get_text(row, 'answer')
                
                if qid in questions_map:
                    questions_map[qid]['levels'][code] = answer

    # 3. Construct Prism JSON
    prism_json = {}
    
    # We need to handle subquestions (if any). 
    # In LimeSurvey, subquestions have a parent_qid != 0.
    # For now, let's treat them as separate entries or try to group them.
    # Prism usually expects a flat list of columns (keys) in the sidecar.
    
    for qid, q_data in questions_map.items():
        key = q_data['title']

        entry = {
            "Description": q_data['question']
        }

        if q_data['levels']:
            entry["Levels"] = q_data['levels']

        prism_json[key] = entry

    normalized_task = sanitize_task_name(task_name or "survey")
    metadata = {
        "Technical": {
            "StimulusType": "Survey",
            "FileFormat": "tsv",
            "SoftwarePlatform": "LimeSurvey",
            "Language": "en",
            "Respondent": "self",
            "ResponseType": ["online"],
        },
        "Study": {
            "TaskName": normalized_task,
            "OriginalName": normalized_task,
            "Version": "1.0",
            "Description": f"Imported from LimeSurvey task {normalized_task}",
        },
        "Metadata": {
            "SchemaVersion": "1.0.0",
            "CreationDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "Creator": "limesurvey_to_prism.py",
        },
    }

    metadata.update(prism_json)
    return metadata


def convert_lsa_to_prism(lsa_path, output_path=None, task_name=None):
    """Extract .lss from .lsa/.lss and convert to a Prism JSON sidecar."""
    if not os.path.exists(lsa_path):
        print(f"File not found: {lsa_path}")
        return

    xml_content = None

    if lsa_path.endswith('.lsa'):
        try:
            with zipfile.ZipFile(lsa_path, 'r') as zip_ref:
                lss_files = [f for f in zip_ref.namelist() if f.endswith('.lss')]
                if not lss_files:
                    print("No .lss file found in the archive.")
                    return

                target_file = lss_files[0]
                print(f"Processing {target_file} from archive...")
                with zip_ref.open(target_file) as f:
                    xml_content = f.read()
        except zipfile.BadZipFile:
            print("Invalid zip file.")
            return
    elif lsa_path.endswith('.lss'):
        with open(lsa_path, 'rb') as f:
            xml_content = f.read()
    else:
        print("Unsupported file extension. Please provide .lsa or .lss")
        return

    if xml_content:
        prism_data = parse_lss_xml(xml_content, task_name)

        if prism_data:
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(prism_data, f, indent=4, ensure_ascii=False)
                print(f"Successfully wrote Prism JSON to {output_path}")
            else:
                print(json.dumps(prism_data, indent=4, ensure_ascii=False))


def convert_lsa_to_dataset(
    lsa_path,
    output_root,
    session_label,
    library_path,
    task_name=None,
    id_priority=None,
    id_column=None,
    id_map=None,
):
    """Convert .lsa responses into a PRISM/BIDS dataset (tsv + json) using survey_library schemas."""
    base_priority = ["participant_id", "id", "code", "token", "subject"]
    if id_column:
        # Fail fast if the requested ID column is missing; do not silently fall back.
        df_preview, questions_map, groups_map = parse_lsa_responses(lsa_path)
        match = next((c for c in df_preview.columns if c.lower() == id_column.lower()), None)
        if not match:
            available = ", ".join(df_preview.columns)
            raise ValueError(
                f"ID column '{id_column}' not found in LimeSurvey responses. Available columns: {available}"
            )
        # Ensure we still process the full dataframe below without re-reading from disk.
        df = df_preview
        id_priority = [match] + base_priority
    else:
        df, questions_map, groups_map = parse_lsa_responses(lsa_path)
        id_priority = id_priority or base_priority

    # Pick participant id column
    id_col = None
    for cand in id_priority:
        for col in df.columns:
            if col.lower() == cand.lower():
                id_col = col
                break
        if id_col:
            break
    if not id_col:
        # Fallback: first column
        id_col = df.columns[0]
    df = df.rename(columns={id_col: "participant_id"})
    
    # Apply ID mapping if provided
    if id_map:
        # Normalize IDs as strings
        df["participant_id"] = df["participant_id"].astype(str).str.strip()

        # Prepare mapping keys (also normalized)
        map_keys = set(str(k).strip() for k in id_map.keys())

        # Find any LimeSurvey IDs present in the data that are not covered by the mapping
        ids_in_data = set(df["participant_id"].unique())
        missing = sorted([i for i in ids_in_data if i not in map_keys])
        if missing:
            # Abort rather than silently keeping unmapped IDs
            sample = ", ".join(missing[:50])
            more = "..." if len(missing) > 50 else ""
            raise ValueError(
                f"ID mapping incomplete: {len(missing)} LimeSurvey IDs are missing mapping entries: {sample}{more}.\n"
                "Please update your ID mapping file so every LimeSurvey ID has a corresponding participant_id."
            )

        # All IDs covered: apply mapping
        df["participant_id"] = df["participant_id"].apply(lambda x: id_map.get(x, x))

    df["participant_id"] = df["participant_id"].apply(
        lambda x: f"sub-{x}" if pd.notna(x) and not str(x).startswith("sub-") else x
    )
    df["session"] = session_label

    # --- Calculate Survey Duration and Start Time ---
    # LimeSurvey typically provides 'startdate' and 'submitdate'
    if "startdate" in df.columns and "submitdate" in df.columns:
        try:
            start = pd.to_datetime(df["startdate"], errors="coerce")
            submit = pd.to_datetime(df["submitdate"], errors="coerce")
            
            # Duration in minutes
            df["SurveyDuration"] = (submit - start).dt.total_seconds() / 60.0
            # Round to 2 decimals
            df["SurveyDuration"] = df["SurveyDuration"].round(2)
            
            # Start Time (HH:MM:SS)
            df["SurveyStartTime"] = start.dt.strftime("%H:%M:%S")
        except Exception as e:
            print(f"Warning: Could not calculate duration/time: {e}")

    # --- Merge Group Timings ---
    try:
        timings_df = parse_lsa_timings(lsa_path)
        
        group_duration_fields = {}
        if timings_df is not None and not timings_df.empty:
            # Rename columns using groups_map
            # Pattern: _[SurveyID]X[GroupID]time
            new_cols = {}
            for col in timings_df.columns:
                # Remove leading underscore if present (xml tags often have it)
                clean_col = col.lstrip('_')
                # Regex to find GroupID before 'time'
                # The format is SurveyID X GroupID time. e.g. 244841X43550time
                m = re.match(r'\d+X(\d+)time', clean_col)
                if m:
                    gid = m.group(1)
                    if gid in groups_map:
                        title = groups_map[gid]
                        # Sanitize title for column name
                        safe_title = "".join(c if c.isalnum() else "_" for c in title)
                        col_name = f"Duration_{safe_title}"
                        new_cols[col] = col_name
                        group_duration_fields[col_name] = {
                            "Description": f"Duration for question group '{title}'",
                            "Units": "seconds"
                        }
            
            if new_cols:
                timings_df = timings_df.rename(columns=new_cols)
                # Keep only the renamed columns
                # Use set to avoid duplicates if multiple groups map to same title (should be rare now)
                # Filter columns that exist in timings_df (after rename)
                timings_df = timings_df.loc[:, ~timings_df.columns.duplicated()]
                
                # Convert to numeric (seconds)
                for c in timings_df.columns:
                    if c.startswith("Duration_"):
                        timings_df[c] = pd.to_numeric(timings_df[c], errors='coerce')
                
                # Merge by index (assuming row alignment)
                if len(df) == len(timings_df):
                    df = pd.concat([df, timings_df], axis=1)
                else:
                    print(f"Warning: Timings row count ({len(timings_df)}) does not match responses ({len(df)}). Skipping timings.")
    except Exception as e:
        print(f"Error processing timings: {e}")
        # Continue without timings
        pass

    task_hint = task_name or sanitize_task_name(Path(lsa_path).stem)
    schemas = load_schemas(library_path)
    if not schemas:
        print(f"No schemas found in {library_path}, cannot build dataset.")
        return

    # Create a dedicated 'limesurvey' task for session-level metadata
    # instead of injecting it into every questionnaire.
    schemas["limesurvey"] = {
        "Technical": {
            "Description": "General metadata for the LimeSurvey session"
        },
        "SurveyDuration": {
            "Description": "Total duration of the LimeSurvey session in minutes (submitdate - startdate)",
            "Units": "minutes"
        },
        "SurveyStartTime": {
            "Description": "Start time of the LimeSurvey session (HH:MM:SS)",
            "Units": "hh:mm:ss"
        },
        **group_duration_fields
    }

    # process_dataframe will copy needed sidecars into rawdata
    # We iterate manually to inject task-specific durations if available
    for t_name, t_schema in schemas.items():
        # Skip the internal 'limesurvey' metadata container; it's not a task to be exported.
        if t_name == "limesurvey":
            continue

        # Work on a copy to avoid side effects between tasks
        task_df = df.copy()
        
        # 1. Check for granular duration
        # Strategy: Find which group the task's variables belong to.
        # Get variables in this task
        task_vars = [k for k in t_schema.keys() if k not in ["Technical", "Study", "Metadata"]]
        
        # Find which group these variables belong to
        gids = []
        # Optimization: Create a map of title -> gid
        title_to_gid = {v['title']: v['gid'] for v in questions_map.values()}
        
        for var in task_vars:
            if var in title_to_gid:
                gids.append(title_to_gid[var])
            else:
                # Fallback: check for prefix match (e.g. ADS01 -> ADS)
                # We look for the longest matching prefix in title_to_gid
                best_match = None
                for title in title_to_gid:
                    if var.startswith(title):
                        if best_match is None or len(title) > len(best_match):
                            best_match = title
                
                if best_match:
                    gids.append(title_to_gid[best_match])
        
        granular_col = None
        if gids:
            # Find mode
            from collections import Counter
            most_common_gid = Counter(gids).most_common(1)[0][0]
            if most_common_gid in groups_map:
                group_title = groups_map[most_common_gid]
                safe_title = "".join(c if c.isalnum() else "_" for c in group_title)
                candidate = f"Duration_{safe_title}"
                if candidate in task_df.columns:
                    granular_col = candidate
        
        # Fallback: try matching task name
        if not granular_col:
            for col in task_df.columns:
                if col.lower() == f"duration_{t_name}".lower():
                    granular_col = col
                    break
        
        if t_name == "ads" and not granular_col:
            pass

        # 2. Inject SurveyDuration/SurveyStartTime into schema if missing
        # This ensures every task gets these columns as requested
        if "SurveyDuration" not in t_schema:
            t_schema["SurveyDuration"] = {
                "Description": f"Duration for task {t_name}",
                "Units": "minutes" # Default to global unit
            }
        if "SurveyStartTime" not in t_schema:
            t_schema["SurveyStartTime"] = {
                "Description": "Start time of the LimeSurvey session (HH:MM:SS)",
                "Units": "hh:mm:ss"
            }

        # 3. Overwrite SurveyDuration with granular data if available
        if granular_col:
            # Granular is in seconds, convert to minutes to match schema unit
            # or update schema unit to seconds.
            # Let's update schema to seconds for precision.
            t_schema["SurveyDuration"]["Units"] = "seconds"
            t_schema["SurveyDuration"]["Description"] = f"Duration for task {t_name} (derived from group timing)"
            task_df["SurveyDuration"] = task_df[granular_col]
            
            # Debug: Compare durations
            try:
                avg_task = pd.to_numeric(task_df[granular_col], errors='coerce').mean()
                avg_global = pd.to_numeric(df["SurveyDuration"], errors='coerce').mean()
                # print(f"  -> Duration Check for {t_name}: Avg Task = {avg_task:.2f}s vs Avg Global = {avg_global:.2f}min")
            except Exception:
                pass
        
        # 4. Process this single task
        # print(f"DEBUG: Processing task {t_name}")
        process_dataframe(task_df, {t_name: t_schema}, output_root, library_path, session_override=session_label)


def load_id_mapping(map_path):
    """Load ID mapping from a TSV/CSV file.
    Expected columns: 'limesurvey_id', 'participant_id' (or first two columns).
    Returns a dict: {str(limesurvey_id): str(participant_id)}
    """
    if not map_path:
        return None
    
    path = Path(map_path)
    if not path.exists():
        print(f"Warning: ID map file {path} not found.")
        return None
    
    try:
        sep = '\t' if path.suffix.lower() == '.tsv' else ','
        df = pd.read_csv(path, sep=sep, dtype=str)
        
        # Try to find standard columns, else take first two
        src_col = next((c for c in df.columns if c.lower() in ['limesurvey_id', 'source_id', 'code', 'id']), None)
        dst_col = next((c for c in df.columns if c.lower() in ['participant_id', 'bids_id', 'sub_id', 'subject_id']), None)
        
        if not src_col or not dst_col:
            if len(df.columns) >= 2:
                src_col = df.columns[0]
                dst_col = df.columns[1]
            else:
                print(f"Warning: ID map file {path} must have at least 2 columns.")
                return None
        
        # Create dict
        mapping = dict(zip(df[src_col], df[dst_col]))
        # Clean up destination: remove 'sub-' prefix if present, as it's added later? 
        # Actually, the code adds 'sub-' if missing. 
        # If mapping has 'sub-123', code sees it starts with 'sub-' and leaves it.
        # If mapping has '123', code adds 'sub-'.
        # So we just pass the value as is.
        return mapping
    except Exception as e:
        print(f"Error loading ID map {path}: {e}")
        return None


def batch_convert_lsa(input_root, output_root, session_map, library_path, task_fallback=None, id_column=None, id_map_file=None):
    """Batch-convert .lsa/.lss under input_root into BIDS/PRISM datasets using survey library."""
    input_root = Path(input_root)
    output_root = Path(output_root)

    id_map = load_id_mapping(id_map_file)
    if id_map:
        print(f"Loaded {len(id_map)} ID mappings from {id_map_file}")

    files = list(input_root.rglob("*.lsa")) + list(input_root.rglob("*.lss"))
    if not files:
        print(f"No .lsa/.lss files found under {input_root}")
        return

    normalized_map = {k.lower(): v for k, v in session_map.items()}

    for lsa_file in files:
        parts_lower = [p.name.lower() for p in lsa_file.parents]
        stem_lower = lsa_file.stem.lower()
        session_raw = next((p for p in parts_lower if p in normalized_map), None)
        if not session_raw:
            session_raw = next((k for k in normalized_map if k in stem_lower), None)
        if not session_raw:
            print(
                f"Skipping {lsa_file}: no session key found (looked for {list(normalized_map.keys())}) in path or filename."
            )
            continue
        session_label = normalized_map[session_raw]

        task_hint = lsa_file.stem
        for raw in normalized_map.keys():
            task_hint = re.sub(fr"[_\-]{raw}$", "", task_hint, flags=re.IGNORECASE)
        task_name = sanitize_task_name(task_hint if task_hint else (task_fallback or "survey"))

        print(f"Converting {lsa_file} -> session {session_label}, task {task_name}")
        convert_lsa_to_dataset(
            str(lsa_file),
            str(output_root),
            session_label,
            library_path,
            task_name=task_name,
            id_column=id_column,
            id_map=id_map,
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert LimeSurvey .lsa/.lss to Prism JSON sidecar.")
    parser.add_argument("input_file", help="Path to .lsa or .lss file")
    parser.add_argument("-o", "--output", help="Path to output .json file")
    
    args = parser.parse_args()
    
    convert_lsa_to_prism(args.input_file, args.output)
