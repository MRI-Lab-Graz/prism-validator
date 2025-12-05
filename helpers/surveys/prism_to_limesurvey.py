#!/usr/bin/env python3
"""
Convert Prism/BIDS JSON sidecar to LimeSurvey Structure File (.lss).

Usage:
    python prism_to_limesurvey.py <input_sidecar.json> [output_structure.lss]

This script allows you to define your questionnaire in a clean JSON format
and automatically generate the importable LimeSurvey structure.
"""

import sys
import os
import json
import argparse
import zipfile
import io
import xml.etree.ElementTree as ET
from datetime import datetime


def create_cdata(text):
    """Helper to create CDATA-like text (LimeSurvey uses HTML entities often)"""
    return text if text else ""


def add_row(parent, data):
    """Add a <row> element with child tags based on dictionary"""
    row = ET.SubElement(parent, "row")
    for key, value in data.items():
        child = ET.SubElement(row, key)
        # CDATA handling is tricky in ElementTree, we'll just set text
        # LimeSurvey is usually fine with standard XML escaping
        child.text = str(value)


def json_to_lss(json_path, output_path, matrix_mode=False):
    with open(json_path, "r") as f:
        data = json.load(f)

    # Filter out metadata keys
    questions = {
        k: v
        for k, v in data.items()
        if k not in ["Technical", "Study", "Metadata", "Categories", "TaskName"]
    }

    # IDs
    sid = "123456"  # Dummy Survey ID
    gid = "10"  # Dummy Group ID

    # Root element
    root = ET.Element("document")
    ET.SubElement(root, "LimeSurveyDocType").text = "Survey"
    ET.SubElement(root, "DBVersion").text = "366"  # Approximate version

    # Languages
    langs = ET.SubElement(root, "languages")
    ET.SubElement(langs, "language").text = "en"

    # 1. ANSWERS Section (Collect all unique answer sets to generate IDs)
    # We need to generate answer entries for questions with 'Levels'
    answers_elem = ET.SubElement(root, "answers")
    answers_rows = ET.SubElement(answers_elem, "rows")

    # 2. QUESTIONS Section
    questions_elem = ET.SubElement(root, "questions")
    questions_rows = ET.SubElement(questions_elem, "rows")

    # 3. GROUPS Section
    groups_elem = ET.SubElement(root, "groups")
    groups_rows = ET.SubElement(groups_elem, "rows")

    # 4. SUBQUESTIONS Section
    subquestions_elem = ET.SubElement(root, "subquestions")
    subquestions_rows = ET.SubElement(subquestions_elem, "rows")

    # Add the single group
    add_row(
        groups_rows,
        {
            "gid": gid,
            "sid": sid,
            "group_name": data.get("TaskName", "Questionnaire"),
            "group_order": "0",
            "description": "",
            "language": "en",
            "randomization_group": "",
            "grelevance": "",
        },
    )

    # Prepare Groups of Questions
    grouped_questions = []
    if matrix_mode:
        current_group = []
        last_levels_str = None

        for q_code, q_data in questions.items():
            if not isinstance(q_data, dict):
                continue

            levels = q_data.get("Levels", {})
            # Only group if levels exist. Text questions shouldn't be grouped this way usually.
            levels_str = json.dumps(levels, sort_keys=True) if levels else "NO_LEVELS"

            if not current_group:
                current_group.append((q_code, q_data))
                last_levels_str = levels_str
            else:
                # Check if matches previous
                if levels and levels_str == last_levels_str:
                    current_group.append((q_code, q_data))
                else:
                    # Flush current group
                    grouped_questions.append(current_group)
                    # Start new
                    current_group = [(q_code, q_data)]
                    last_levels_str = levels_str

        if current_group:
            grouped_questions.append(current_group)
    else:
        # No grouping
        for q_code, q_data in questions.items():
            if isinstance(q_data, dict):
                grouped_questions.append([(q_code, q_data)])

    # Process Questions
    qid_counter = 100
    sort_order = 0

    for group in grouped_questions:
        # group is a list of (q_code, q_data)

        # Common data from first item
        first_code, first_data = group[0]
        levels = first_data.get("Levels", {})

        # Determine if it's a Matrix or Single
        is_matrix = (len(group) > 1)

        qid = str(qid_counter)
        qid_counter += 1
        sort_order += 1

        # Logic / Relevance
        # Check for "Relevance" key directly, or inside a "LimeSurvey" object
        relevance = "1"  # Default: Always visible
        if "Relevance" in first_data:
            relevance = first_data["Relevance"]
        elif "LimeSurvey" in first_data and "Relevance" in first_data["LimeSurvey"]:
            relevance = first_data["LimeSurvey"]["Relevance"]

        if is_matrix:
            # Matrix Question (Array)
            # Type 'F' is Array (Flexible Labels)
            q_type = "F"

            # Matrix Title
            matrix_title = f"M_{first_code}"

            # Matrix Text - Use a generic prompt
            matrix_text = "Please answer the following questions:"

            add_row(
                questions_rows,
                {
                    "qid": qid,
                    "parent_qid": "0",
                    "sid": sid,
                    "gid": gid,
                    "type": q_type,
                    "title": matrix_title,
                    "question": matrix_text,
                    "other": "N",
                    "mandatory": "Y",
                    "question_order": str(sort_order),
                    "language": "en",
                    "scale_id": "0",
                    "same_default": "0",
                    "relevance": relevance,
                },
            )

            # Add Subquestions
            sub_sort = 0
            for code, data_item in group:
                sub_sort += 1
                sub_qid = str(qid_counter)
                qid_counter += 1

                add_row(
                    subquestions_rows,
                    {
                        "qid": sub_qid,
                        "parent_qid": qid,
                        "sid": sid,
                        "gid": gid,
                        "type": "T",
                        "title": code,
                        "question": data_item.get("Description", code),
                        "question_order": str(sub_sort),
                        "language": "en",
                        "scale_id": "0",
                        "same_default": "0",
                        "relevance": "1",
                    },
                )

            # Add Answers (Only once for the matrix parent)
            if levels:
                sort_ans = 0
                for code, answer_text in levels.items():
                    sort_ans += 1
                    add_row(
                        answers_rows,
                        {
                            "qid": qid,
                            "code": code,
                            "answer": answer_text,
                            "sortorder": str(sort_ans),
                            "language": "en",
                            "assessment_value": "0",
                            "scale_id": "0",
                        },
                    )

        else:
            # Single Question
            q_code = first_code
            q_data = first_data
            description = q_data.get("Description", q_code)

            # Determine Type
            # L = List (Radio) - if levels exist
            # T = Long Free Text - if no levels
            q_type = "L" if levels else "T"

            # Add Question Row
            add_row(
                questions_rows,
                {
                    "qid": qid,
                    "parent_qid": "0",
                    "sid": sid,
                    "gid": gid,
                    "type": q_type,
                    "title": q_code,
                    "question": description,
                    "other": "N",
                    "mandatory": "Y",
                    "question_order": str(sort_order),
                    "language": "en",
                    "scale_id": "0",
                    "same_default": "0",
                    "relevance": relevance,
                },
            )

            # Add Answers if applicable
            if levels:
                sort_ans = 0
                for code, answer_text in levels.items():
                    sort_ans += 1
                    add_row(
                        answers_rows,
                        {
                            "qid": qid,
                            "code": code,
                            "answer": answer_text,
                            "sortorder": str(sort_ans),
                            "language": "en",
                            "assessment_value": "0",
                            "scale_id": "0",
                        },
                    )

    # 5. SURVEYS Section (General Settings)
    surveys_elem = ET.SubElement(root, "surveys")
    surveys_rows = ET.SubElement(surveys_elem, "rows")

    add_row(
        surveys_rows,
        {
            "sid": sid,
            "gsid": "1",
            "admin": "Administrator",
            "active": "N",
            "anonymized": "N",
            "format": "G",  # Group by Group
            "savetimings": "Y",
            "template": "vanilla",
            "language": "en",
        },
    )

    # 6. SURVEY_LANGUAGESETTINGS (Title, etc.)
    surveys_lang_elem = ET.SubElement(root, "surveys_languagesettings")
    surveys_lang_rows = ET.SubElement(surveys_lang_elem, "rows")

    add_row(
        surveys_lang_rows,
        {
            "surveyls_survey_id": sid,
            "surveyls_language": "en",
            "surveyls_title": data.get("TaskName", "Generated Survey"),
            "surveyls_description": f"Generated from Prism JSON on {datetime.now().isoformat()}",
            "surveyls_welcometext": "",
            "surveyls_endtext": "",
        },
    )

    # Write to file
    tree = ET.ElementTree(root)
    # Indent for readability (Python 3.9+)
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ", level=0)

    if output_path.endswith('.lsa'):
        # Create LSA archive (Zip file containing .lss)
        # We need to write the XML to a buffer first
        xml_buffer = io.BytesIO()
        tree.write(xml_buffer, encoding="UTF-8", xml_declaration=True)
        xml_content = xml_buffer.getvalue()
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
            # The .lss file inside the archive usually has the same name as the archive or 'survey_archive.lss'
            lss_filename = os.path.basename(output_path).replace('.lsa', '.lss')
            z.writestr(lss_filename, xml_content)
            
        print(f"Successfully created LSA archive {output_path}")
    else:
        # Standard LSS file
        tree.write(output_path, encoding="UTF-8", xml_declaration=True)
        print(f"Successfully created {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Prism/BIDS JSON sidecar to LimeSurvey Structure File (.lss) or Archive (.lsa)."
    )
    parser.add_argument("input_json", help="Path to the input JSON sidecar file")
    parser.add_argument(
        "output_lss",
        nargs="?",
        help="Path to the output LSS file (optional, defaults to input name)",
    )
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="Auto-detect and group consecutive questions with identical answer options into Matrix questions",
    )

    args = parser.parse_args()

    json_path = args.input_json
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        sys.exit(1)

    if args.output_lss:
        output_path = args.output_lss
    else:
        base_name = os.path.splitext(os.path.basename(json_path))[0]
        output_path = f"{base_name}.lss"

    json_to_lss(json_path, output_path, matrix_mode=args.matrix)
