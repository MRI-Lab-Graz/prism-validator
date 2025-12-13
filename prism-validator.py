#!/usr/bin/env python3
"""
Prism-Validator: Streamlined main entry point

A modular, BIDS-inspired validation tool for psychological research datasets.
"""

import os
import sys
import argparse

# Check if running inside the venv (skip for frozen/packaged apps)
venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")
if not getattr(sys, "frozen", False) and not sys.prefix.startswith(venv_path):
    print(
        "❌ Error: You are not running inside the prism-validator virtual environment!"
    )
    print("   Please activate the venv first:")
    if os.name == "nt":  # Windows
        print(f"     {venv_path}\\Scripts\\activate")
    else:  # Unix/Mac
        print(f"     source {venv_path}/bin/activate")
    print("   Then run this script again.")
    sys.exit(1)

# Add src directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "src")
sys.path.insert(0, src_path)

try:
    from schema_manager import load_all_schemas
    from validator import DatasetValidator, MODALITY_PATTERNS
    from stats import DatasetStats
    from reporting import print_dataset_summary, print_validation_results
    from bids_integration import check_and_update_bidsignore
    from runner import validate_dataset
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Prism-Validator: BIDS-inspired validation for psychological research data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/dataset
  %(prog)s /path/to/dataset --verbose
  %(prog)s /path/to/dataset --schema-version 0.1
  %(prog)s --schema-info image
        """,
    )

    parser.add_argument("dataset", nargs="?", help="Path to dataset root directory")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed validation information",
    )
    parser.add_argument(
        "--schema-version",
        metavar="VERSION",
        help="Schema version to use (e.g., 'stable', '0.1'). Default: stable",
    )
    parser.add_argument(
        "--schema-info",
        metavar="MODALITY",
        help="Display schema details for a specific modality",
    )
    parser.add_argument(
        "--list-versions", action="store_true", help="List available schema versions"
    )
    parser.add_argument(
        "--bids",
        action="store_true",
        help="Run the standard BIDS validator in addition to PRISM validation",
    )
    parser.add_argument(
        "--bids-warnings",
        action="store_true",
        help="Show warnings from the BIDS validator (default: hidden)",
    )
    parser.add_argument("--version", action="version", version="Prism-Validator 1.3.0")

    args = parser.parse_args()

    # Handle list versions request
    if args.list_versions:
        schema_dir = os.path.join(os.path.dirname(__file__), "schemas")
        from schema_manager import get_available_schema_versions

        versions = get_available_schema_versions(schema_dir)
        print("Available schema versions:")
        for v in versions:
            default_marker = " (default)" if v == "stable" else ""
            print(f"  • {v}{default_marker}")
        return

    # Handle schema info request
    if args.schema_info:
        # Import and show schema info (simplified for this streamlined version)
        print(f"Schema information for modality: {args.schema_info}")
        print("(Use the full prism-validator.py for detailed schema inspection)")
        return

    # Validate required arguments
    if not args.dataset:
        parser.error("Dataset path is required")

    if not os.path.exists(args.dataset):
        print(f"❌ Dataset directory not found: {args.dataset}")
        sys.exit(1)

    # Run validation with schema version
    schema_version = args.schema_version or "stable"
    print(f"🔍 Validating dataset: {args.dataset}")
    if args.schema_version:
        print(f"📋 Using schema version: {schema_version}")

    try:
        issues, stats = validate_dataset(
            args.dataset,
            verbose=args.verbose,
            schema_version=schema_version,
            run_bids=args.bids,
        )

        # Print results
        print_dataset_summary(args.dataset, stats)
        print_validation_results(issues, show_bids_warnings=args.bids_warnings)

        # Exit with appropriate code
        error_count = sum(1 for level, _ in issues if level == "ERROR")
        sys.exit(1 if error_count > 0 else 0)

    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
