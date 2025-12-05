#!/usr/bin/env python3
"""
Convert LimeSurvey Structure File (.lss/.xml) to Prism/BIDS JSON sidecar.

Usage:
    python limesurvey_to_prism.py <limesurvey_structure.lss> [output_filename.json]

This script parses a LimeSurvey XML export and generates a JSON sidecar
compatible with the Prism-Validator survey schema.
"""

import sys
import os
import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import date


def parse_limesurvey_structure(lss_path):
    """
    Parse LimeSurvey .lss (XML) file or .lsa (Archive) and extract question metadata.
    """
    try:
        if lss_path.endswith('.lsa'):
            with zipfile.ZipFile(lss_path, 'r') as z:
                # Find the .lss file inside the archive
                lss_files = [f for f in z.namelist() if f.endswith('.lss')]
                if not lss_files:
                    print("Error: No .lss file found in the .lsa archive.")
                    sys.exit(1)
                # Use the first .lss file found
                with z.open(lss_files[0]) as f:
                    tree = ET.parse(f)
        else:
            tree = ET.parse(lss_path)
            
        root = tree.getroot()
    except (ET.ParseError, zipfile.BadZipFile) as e:
        print(f"Error parsing file: {e}")
        sys.exit(1)

    # LimeSurvey XML structure usually has sections for questions, subquestions, answers
    # We need to iterate through them. The structure can be complex.
    # Simplified approach: Look for 'questions' rows

    # Map question IDs (qid) to their codes and text
    q_map = {}

    # Find all 'rows' in 'questions' section
    # Structure: <questions> <rows> <row> <qid>...</qid> <title>...</title> <question>...</question> ... </row> ... </rows> </questions>

    for row in root.findall(".//questions/rows/row"):
        qid = row.find("qid").text
        code = row.find("title").text  # This is the variable name (e.g. Q01)
        text = row.find("question").text
        q_type = row.find("type").text

        # Clean up text (remove HTML tags if present)
        if text:
            # Simple tag removal
            text = "".join(ET.fromstring(f"<root>{text}</root>").itertext())

        q_map[qid] = {"code": code, "text": text, "type": q_type, "answers": {}}

    # Find subquestions (for array types)
    # <subquestions> <rows> <row> <parent_qid>...</parent_qid> <title>...</title> <question>...</question> ...
    for row in root.findall(".//subquestions/rows/row"):
        parent_qid = row.find("parent_qid").text
        code = row.find("title").text  # Subquestion code (e.g. SQ001)
        text = row.find("question").text

        if parent_qid in q_map:
            if "subquestions" not in q_map[parent_qid]:
                q_map[parent_qid]["subquestions"] = []

            q_map[parent_qid]["subquestions"].append({"code": code, "text": text})

    # Find answers (for list/radio types)
    # <answers> <rows> <row> <qid>...</qid> <code>...</code> <answer>...</answer> ...
    for row in root.findall(".//answers/rows/row"):
        qid = row.find("qid").text
        code = row.find("code").text
        answer = row.find("answer").text

        if qid in q_map:
            q_map[qid]["answers"][code] = answer

    # Convert to Prism format
    prism_questions = {}

    for qid, q_data in q_map.items():
        # Handle different question types
        # Simple questions
        if "subquestions" not in q_data:
            key = q_data["code"]
            entry = {"Description": q_data["text"]}
            if q_data["answers"]:
                entry["Levels"] = q_data["answers"]

            prism_questions[key] = entry

        # Array questions (multiple subquestions sharing same answers)
        else:
            parent_code = q_data["code"]
            for sub in q_data["subquestions"]:
                # Construct key: Parent_Sub (e.g. Q01_SQ001)
                # LimeSurvey export usually combines them in the data CSV as Parent_Sub
                key = f"{parent_code}_{sub['code']}"
                entry = {"Description": f"{q_data['text']} - {sub['text']}"}
                if q_data["answers"]:
                    entry["Levels"] = q_data["answers"]

                prism_questions[key] = entry

    return prism_questions


def generate_prism_json(questions, output_path):
    """
    Generate the final Prism JSON sidecar.
    """
    prism_data = {
        **questions,
        "Technical": {
            "StimulusType": "Behavior",
            "FileFormat": "tsv",
            "ResponseType": ["keypress", "mouse_click"],
            "SoftwarePlatform": "LimeSurvey",
        },
        "Study": {
            "Task": "survey",  # Placeholder
            "Subject": "sub-001",  # Placeholder
            "Run": "run-01",  # Placeholder
            "TaskType": "questionnaire",
            "TrialStructure": {"TrialCount": len(questions)},
        },
        "Metadata": {
            "SchemaVersion": "1.0.0",
            "CreationDate": date.today().isoformat(),
            "Creator": "LimeSurvey to Prism Converter",
        },
    }

    with open(output_path, "w") as f:
        json.dump(prism_data, f, indent=2)

    print(f"Successfully created {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python limesurvey_to_prism.py <limesurvey_structure.lss/.lsa> [output_filename.json]"
        )
        sys.exit(1)

    lss_path = sys.argv[1]
    if not os.path.exists(lss_path):
        print(f"File not found: {lss_path}")
        sys.exit(1)

    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        base_name = os.path.splitext(os.path.basename(lss_path))[0]
        output_path = f"task-{base_name}_beh.json"

    questions = parse_limesurvey_structure(lss_path)
    generate_prism_json(questions, output_path)
