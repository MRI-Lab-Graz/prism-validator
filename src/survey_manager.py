import json
import shutil
import os
from pathlib import Path
from datetime import datetime
from library_validator import LibraryValidator


class SurveyManager:
    """
    Manages the "Draft & Publish" workflow for the Survey Library.
    """

    def __init__(self, library_path):
        self.lib_path = Path(library_path)
        self.validator = LibraryValidator(self.lib_path)
        self.drafts_path = self.lib_path / "drafts"
        self.drafts_path.mkdir(parents=True, exist_ok=True)
        self.requests_path = self.lib_path / "merge_requests"
        self.requests_path.mkdir(parents=True, exist_ok=True)

    def list_surveys(self):
        """
        Returns a list of all surveys with their status.
        """
        surveys = {}

        # 1. Scan Golden Masters
        for f in self.lib_path.glob("*.json"):
            surveys[f.name] = {
                "filename": f.name,
                "has_master": True,
                "has_draft": False,
                "master_mtime": datetime.fromtimestamp(f.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                ),
            }

        # 2. Scan Drafts
        for f in self.drafts_path.glob("*.json"):
            if f.name not in surveys:
                surveys[f.name] = {
                    "filename": f.name,
                    "has_master": False,
                    "has_draft": True,
                }
            else:
                surveys[f.name]["has_draft"] = True
            
            surveys[f.name]["draft_mtime"] = datetime.fromtimestamp(f.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M"
            )

        return sorted(surveys.values(), key=lambda x: x["filename"])

    def create_draft(self, filename):
        """
        Copies a master file to the drafts folder.
        """
        master_file = self.lib_path / filename
        draft_file = self.drafts_path / filename

        if not master_file.exists():
            raise FileNotFoundError(f"Master file {filename} not found.")

        shutil.copy2(master_file, draft_file)
        return True

    def get_draft_content(self, filename):
        """
        Reads the content of a draft file.
        """
        draft_file = self.drafts_path / filename
        if not draft_file.exists():
            # If no draft exists, try to read master (view-only mode or auto-create draft)
            # But strictly speaking, we should edit drafts.
            raise FileNotFoundError(f"Draft {filename} not found.")

        with open(draft_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_draft(self, filename, content):
        """
        Saves content to the draft file.
        """
        draft_file = self.drafts_path / filename
        
        # Ensure it's valid JSON before saving
        if isinstance(content, str):
            content = json.loads(content)
            
        with open(draft_file, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
        
        return True

    def publish_draft(self, filename):
        """
        Moves a draft to the merge_requests folder for review.
        Validates the draft before submission.
        """
        draft_file = self.drafts_path / filename
        request_file = self.requests_path / filename

        if not draft_file.exists():
            raise FileNotFoundError(f"Draft {filename} not found.")

        # Validate draft content
        try:
            with open(draft_file, "r", encoding="utf-8") as f:
                content = json.load(f)
            
            errors = self.validator.validate_draft(content, filename)
            if errors:
                raise ValueError("Validation failed:\n" + "\n".join(errors))
                
        except json.JSONDecodeError:
            raise ValueError(f"Draft {filename} contains invalid JSON.")

        # Move draft to merge requests folder
        shutil.move(draft_file, request_file)
        return True

    def discard_draft(self, filename):
        """
        Deletes a draft file.
        """
        draft_file = self.drafts_path / filename
        if draft_file.exists():
            os.remove(draft_file)
            return True
        return False
