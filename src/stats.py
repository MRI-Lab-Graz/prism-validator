"""
Dataset statistics and consistency checking
"""

import re


class DatasetStats:
    """Collect and analyze dataset statistics"""

    def __init__(self):
        self.subjects = set()
        self.sessions = set()
        self.modalities = {}  # modality -> file count
        self.tasks = set()
        self.surveys = set()
        self.biometrics = set()
        self.descriptions = {}  # type -> name -> description
        self.total_files = 0
        self.sidecar_files = 0
        # For consistency checking
        self.subject_data = {}  # subject_id -> {sessions: {}, modalities: set(), tasks: set()}

    def add_file(self, subject_id, session_id, modality, task, filename):
        """Add a file to the statistics"""
        self.subjects.add(subject_id)
        if session_id:
            self.sessions.add(f"{subject_id}/{session_id}")
        if modality not in self.modalities:
            self.modalities[modality] = 0
        self.modalities[modality] += 1
        if task:
            self.tasks.add(task)

        if modality == "survey":
            if task:
                self.surveys.add(task)
            match = re.search(r"_survey-([a-zA-Z0-9]+)", filename)
            if match:
                self.surveys.add(match.group(1))

        if modality == "biometrics":
            if task:
                self.biometrics.add(task)
            match = re.search(r"_biometrics-([a-zA-Z0-9]+)", filename)
            if match:
                self.biometrics.add(match.group(1))

        self.total_files += 1

        # Check for sidecar
        if filename.endswith(".json"):
            self.sidecar_files += 1

        # Track per-subject data for consistency checking
        if subject_id not in self.subject_data:
            self.subject_data[subject_id] = {
                "sessions": set(),
                "modalities": set(),
                "tasks": set(),
                "session_data": {},  # session_id -> {modalities: set(), tasks: set()}
            }

        subject_info = self.subject_data[subject_id]
        subject_info["modalities"].add(modality)
        if task:
            subject_info["tasks"].add(task)

        if session_id:
            subject_info["sessions"].add(session_id)
            if session_id not in subject_info["session_data"]:
                subject_info["session_data"][session_id] = {
                    "modalities": set(),
                    "tasks": set(),
                }
            subject_info["session_data"][session_id]["modalities"].add(modality)
            if task:
                subject_info["session_data"][session_id]["tasks"].add(task)

    def add_description(self, entity_type, name, description):
        """Store description (OriginalName) for an entity"""
        if not description:
            return
        if entity_type not in self.descriptions:
            self.descriptions[entity_type] = {}
        # Only set if not already set (or overwrite? let's overwrite to be safe)
        self.descriptions[entity_type][name] = description

    def get_description(self, entity_type, name):
        """Get stored description"""
        return self.descriptions.get(entity_type, {}).get(name)

    def check_consistency(self):
        """Check for consistency across subjects and return warnings"""
        warnings = []

        if len(self.subjects) < 2:
            return warnings  # Can't check consistency with less than 2 subjects

        # Separate subjects with and without sessions
        subjects_with_sessions = {}
        subjects_without_sessions = {}

        for subject_id, data in self.subject_data.items():
            if data["sessions"]:
                subjects_with_sessions[subject_id] = data
            else:
                subjects_without_sessions[subject_id] = data

        # Check consistency within session-based subjects
        if len(subjects_with_sessions) > 1:
            warnings.extend(self._check_session_consistency(subjects_with_sessions))

        # Check consistency within non-session subjects
        if len(subjects_without_sessions) > 1:
            warnings.extend(
                self._check_non_session_consistency(subjects_without_sessions)
            )

        # Warn if mixing session and non-session structures
        if subjects_with_sessions and subjects_without_sessions:
            warnings.append(
                (
                    "WARNING",
                    f"Mixed session structure: {len(subjects_with_sessions)} subjects have sessions, "
                    f"{len(subjects_without_sessions)} don't",
                )
            )

        return warnings

    def _check_session_consistency(self, subjects_with_sessions):
        """Check consistency among subjects with sessions"""
        warnings = []

        # Find all unique sessions across subjects
        all_sessions = set()
        for data in subjects_with_sessions.values():
            all_sessions.update(data["sessions"])

        # Aggregate missing sessions across subjects to reduce noise
        missing_by_session = {}

        for subject_id, data in subjects_with_sessions.items():
            missing_sessions = all_sessions - data["sessions"]
            for session in missing_sessions:
                missing_by_session.setdefault(session, []).append(subject_id)

        for session in sorted(missing_by_session.keys()):
            subjects = sorted(missing_by_session[session])
            warnings.append(
                (
                    "WARNING",
                    f"Session {session} missing for subjects: {', '.join(subjects)}",
                )
            )

        return warnings

    def _check_non_session_consistency(self, subjects_without_sessions):
        """Check consistency among subjects without sessions"""
        warnings = []

        # Find all modalities and tasks across subjects
        all_modalities = set()
        all_tasks = set()
        for data in subjects_without_sessions.values():
            all_modalities.update(data["modalities"])
            all_tasks.update(data["tasks"])

        # Check each subject has all modalities and tasks
        for subject_id, data in subjects_without_sessions.items():
            missing_modalities = all_modalities - data["modalities"]
            missing_tasks = all_tasks - data["tasks"]

            for modality in missing_modalities:
                warnings.append(
                    ("WARNING", f"Subject {subject_id} missing {modality} data")
                )

            for task in missing_tasks:
                warnings.append(
                    ("WARNING", f"Subject {subject_id} missing task {task}")
                )

        return warnings
