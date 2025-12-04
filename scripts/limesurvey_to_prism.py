import argparse
import zipfile
import xml.etree.ElementTree as ET
import json
import os
import sys
import re

def parse_lss_xml(xml_content):
    """
    Parses the LimeSurvey .lss XML content and returns a dictionary
    representing the Prism JSON sidecar structure.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None

    # Helper to find text of a child element
    def get_text(element, tag):
        child = element.find(tag)
        return child.text if child is not None else ""

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
                clean_question = re.sub('<[^<]+?>', '', question_text).strip()
                
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
        # Skip subquestions for a moment to see how they look? 
        # Actually, if it's a subquestion, the 'title' might be the sub-code (e.g. 'SQ001').
        # The full variable name in LimeSurvey export is usually ParentTitle_SubTitle.
        # But here we only have the raw structure.
        
        # Let's just use the 'title' as the key.
        key = q_data['title']
        
        entry = {
            "Description": q_data['question']
        }
        
        if q_data['levels']:
            entry["Levels"] = q_data['levels']
            
        prism_json[key] = entry

    return prism_json

def convert_lsa_to_prism(lsa_path, output_path=None):
    """
    Extracts .lss from .lsa and converts to Prism JSON.
    """
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
        prism_data = parse_lss_xml(xml_content)
        
        if prism_data:
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(prism_data, f, indent=4, ensure_ascii=False)
                print(f"Successfully wrote Prism JSON to {output_path}")
            else:
                print(json.dumps(prism_data, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert LimeSurvey .lsa/.lss to Prism JSON sidecar.")
    parser.add_argument("input_file", help="Path to .lsa or .lss file")
    parser.add_argument("-o", "--output", help="Path to output .json file")
    
    args = parser.parse_args()
    
    convert_lsa_to_prism(args.input_file, args.output)
