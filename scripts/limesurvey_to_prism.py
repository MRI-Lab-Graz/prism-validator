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
    """Return (dataframe, qid->title mapping) extracted from a LimeSurvey .lsa file."""
    with zipfile.ZipFile(lsa_path, "r") as z:
        xml_resp = z.read(next(n for n in z.namelist() if n.endswith("_responses.lsr")))
        xml_lss = z.read(next(n for n in z.namelist() if n.endswith(".lss")))

    lss_root = ET.fromstring(xml_lss)
    qid_to_title = {}
    for row in lss_root.findall(".//questions/rows/row"):
        qid = row.find("qid").text
        title = row.find("title").text
        qid_to_title[qid] = title
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

    return df, qid_to_title


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

    # 1. Parse Questions
    # Map qid -> {title, question, type, ...}
    questions_map = {}
    
    # Find the <questions> section
    questions_section = root.find('questions')
    if questions_section is not None:
        rows = questions_section.find('rows')
        if rows is not None:
            for row in rows.findall('row'):
                qid = get_text(row, 'qid')
                title = get_text(row, 'title') # This is usually the variable name (e.g. 'age', 'gender')
                question_text = get_text(row, 'question')
                q_type = get_text(row, 'type')
                parent_qid = get_text(row, 'parent_qid')
                
                # Clean up CDATA or HTML tags from question text if necessary
                # (Simple strip for now, maybe more complex later)
                # Remove HTML tags
                clean_question = re.sub('<[^<]+?>', '', question_text or '').strip()
                
                questions_map[qid] = {
                    'title': title,
                    'question': clean_question,
                    'type': q_type,
                    'parent_qid': parent_qid,
                    'levels': {}
                }

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
):
    """Convert .lsa responses into a PRISM/BIDS dataset (tsv + json) using survey_library schemas."""
    base_priority = ["participant_id", "id", "code", "token", "subject"]
    if id_column:
        # Fail fast if the requested ID column is missing; do not silently fall back.
        df_preview, _ = parse_lsa_responses(lsa_path)
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
        df, _ = parse_lsa_responses(lsa_path)
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
    df["participant_id"] = df["participant_id"].apply(
        lambda x: f"sub-{x}" if pd.notna(x) and not str(x).startswith("sub-") else x
    )
    df["session"] = session_label

    task_hint = task_name or sanitize_task_name(Path(lsa_path).stem)
    schemas = load_schemas(library_path)
    if not schemas:
        print(f"No schemas found in {library_path}, cannot build dataset.")
        return

    # process_dataframe will copy needed sidecars into rawdata
    process_dataframe(df, schemas, output_root, library_path, session_override=session_label)


def batch_convert_lsa(input_root, output_root, session_map, library_path, task_fallback=None, id_column=None):
    """Batch-convert .lsa/.lss under input_root into BIDS/PRISM datasets using survey library."""
    input_root = Path(input_root)
    output_root = Path(output_root)

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
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert LimeSurvey .lsa/.lss to Prism JSON sidecar.")
    parser.add_argument("input_file", help="Path to .lsa or .lss file")
    parser.add_argument("-o", "--output", help="Path to output .json file")
    
    args = parser.parse_args()
    
    convert_lsa_to_prism(args.input_file, args.output)
