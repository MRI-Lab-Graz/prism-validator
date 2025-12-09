"""
Output formatting and reporting utilities
"""

import os
import json


def get_entity_description(dataset_path, prefix, name, stats=None):
    """Try to fetch OriginalName from sidecar or stats"""
    # Try stats first
    if stats:
        desc = stats.get_description(prefix, name)
        if desc:
            return desc

    # Try root level first: prefix-name.json (e.g. survey-ads.json)
    candidates = [
        os.path.join(dataset_path, f"{prefix}-{name}.json"),
        os.path.join(dataset_path, f"{prefix}s", f"{prefix}-{name}.json"),
        os.path.join(dataset_path, f"{name}.json"),  # Fallback
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "Study" in data and "OriginalName" in data["Study"]:
                        return data["Study"]["OriginalName"]
            except Exception:
                continue
    return None


def print_dataset_summary(dataset_path, stats):
    """Print a comprehensive dataset summary"""
    print("\n" + "=" * 60)
    print("🗂️  DATASET SUMMARY")
    print("=" * 60)

    # Dataset info
    dataset_name = os.path.basename(os.path.abspath(dataset_path))
    print(f"📁 Dataset: {dataset_name}")

    # Subject and session counts
    num_subjects = len(stats.subjects)
    num_sessions = len(stats.sessions)
    has_sessions = num_sessions > 0

    print(f"👥 Subjects: {num_subjects}")
    if has_sessions:
        print(f"📋 Sessions: {num_sessions}")
        # Calculate sessions per subject
        sessions_per_subject = {}
        for session in stats.sessions:
            subj = session.split("/")[0]
            sessions_per_subject[subj] = sessions_per_subject.get(subj, 0) + 1
        avg_sessions = (
            sum(sessions_per_subject.values()) / len(sessions_per_subject)
            if sessions_per_subject
            else 0
        )
        print(f"📊 Sessions per subject: {avg_sessions:.1f} (avg)")
    else:
        print("📋 Sessions: No session structure detected")

    # Modality breakdown
    print(f"\n🎯 MODALITIES ({len(stats.modalities)} found):")
    if stats.modalities:
        for modality, count in sorted(stats.modalities.items()):
            print(f"  • {modality}: {count} files")
    else:
        print("  No modality data found")

    # Task breakdown (exclude items that are surveys or biometrics)
    pure_tasks = {
        t for t in stats.tasks if t not in stats.surveys and t not in stats.biometrics
    }
    print(f"\n📝 TASKS ({len(pure_tasks)} found):")
    if pure_tasks:
        for task in sorted(pure_tasks):
            desc = get_entity_description(dataset_path, "task", task, stats)
            if desc:
                print(f"  • {task} - {desc}")
            else:
                print(f"  • {task}")
    else:
        print("  No tasks detected")

    # Survey breakdown
    print(f"\n📋 SURVEYS ({len(stats.surveys)} found):")
    if stats.surveys:
        for survey in sorted(stats.surveys):
            desc = get_entity_description(dataset_path, "survey", survey, stats)
            if desc:
                print(f"  • {survey} - {desc}")
            else:
                print(f"  • {survey}")
    else:
        print("  No surveys detected")

    # Biometrics breakdown
    print(f"\n🧬 BIOMETRICS ({len(stats.biometrics)} found):")
    if stats.biometrics:
        for biometric in sorted(stats.biometrics):
            desc = get_entity_description(dataset_path, "biometrics", biometric, stats)
            if desc:
                print(f"  • {biometric} - {desc}")
            else:
                print(f"  • {biometric}")
    else:
        print("  No biometrics detected")

    # File statistics intentionally omitted (counts often exclude inherited sidecars and can be misleading)


def print_validation_results(problems):
    """Print validation results with proper categorization"""
    if not problems:
        print("\n" + "=" * 60)
        print("✅ VALIDATION RESULTS")
        print("=" * 60)
        print("🎉 No issues found! Dataset is valid.")
        return

    # Categorize problems
    errors = [msg for level, msg in problems if level == "ERROR"]
    warnings = [msg for level, msg in problems if level == "WARNING"]
    infos = [msg for level, msg in problems if level == "INFO"]

    # Split BIDS vs PRISM
    bids_errors = [e for e in errors if e.startswith("[BIDS]")]
    prism_errors = [e for e in errors if not e.startswith("[BIDS]")]

    bids_warnings = [w for w in warnings if w.startswith("[BIDS]")]
    prism_warnings = [w for w in warnings if not w.startswith("[BIDS]")]

    bids_infos = [i for i in infos if i.startswith("[BIDS]")]
    prism_infos = [i for i in infos if not i.startswith("[BIDS]")]

    print("\n" + "=" * 60)
    print("🔍 VALIDATION RESULTS")
    print("=" * 60)

    # --- PRISM ISSUES ---
    if prism_errors or prism_warnings or prism_infos:
        print("\n🔸 PRISM VALIDATOR REPORT:")

        if prism_errors:
            print(f"\n\033[31m  🔴 ERRORS ({len(prism_errors)}):\033[0m")
            for i, error in enumerate(prism_errors, 1):
                print(f"    \033[31m{i:2d}. {error}\033[0m")

        if prism_warnings:
            print(f"\n\033[33m  🟡 WARNINGS ({len(prism_warnings)}):\033[0m")
            for i, warning in enumerate(prism_warnings, 1):
                print(f"    \033[33m{i:2d}. {warning}\033[0m")

        if prism_infos:
            print(f"\n\033[34m  🔵 INFO ({len(prism_infos)}):\033[0m")
            for i, info in enumerate(prism_infos, 1):
                print(f"    \033[34m{i:2d}. {info}\033[0m")

    # --- BIDS ISSUES ---
    if bids_errors or bids_warnings or bids_infos:
        print("\n🔹 BIDS VALIDATOR REPORT:")

        if bids_errors:
            print(f"\n\033[31m  🔴 ERRORS ({len(bids_errors)}):\033[0m")
            for i, error in enumerate(bids_errors, 1):
                # Strip [BIDS] prefix for cleaner output since we are in BIDS section
                clean_error = error.replace("[BIDS] ", "", 1)
                print(f"    \033[31m{i:2d}. {clean_error}\033[0m")

        if bids_warnings:
            print(f"\n\033[33m  🟡 WARNINGS ({len(bids_warnings)}):\033[0m")
            for i, warning in enumerate(bids_warnings, 1):
                clean_warning = warning.replace("[BIDS] ", "", 1)
                print(f"    \033[33m{i:2d}. {clean_warning}\033[0m")

        if bids_infos:
            print(f"\n\033[34m  🔵 INFO ({len(bids_infos)}):\033[0m")
            for i, info in enumerate(bids_infos, 1):
                clean_info = info.replace("[BIDS] ", "", 1)
                print(f"    \033[34m{i:2d}. {clean_info}\033[0m")

    # Summary line
    print(
        f"\n📊 SUMMARY: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} info"
    )

    if errors:
        print("❌ Dataset validation failed due to errors.")
    else:
        print("⚠️  Dataset has warnings but no critical errors.")
