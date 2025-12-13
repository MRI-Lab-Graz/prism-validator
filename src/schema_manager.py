"""
Schema management for prism-validator
"""

import os
import json

# Default schema version to use when not specified
DEFAULT_SCHEMA_VERSION = "stable"


def parse_version(version_string):
    """Parse semantic version string to tuple of integers"""
    try:
        return tuple(map(int, version_string.split(".")))
    except Exception:
        return (0, 0, 0)


def is_compatible_version(required_version, provided_version):
    """Check if provided version is compatible with required version"""
    req_major, req_minor, req_patch = parse_version(required_version)
    prov_major, prov_minor, prov_patch = parse_version(provided_version)

    # Same major version is required for compatibility
    if req_major != prov_major:
        return False

    # Minor version can be higher (backward compatible)
    if prov_minor < req_minor:
        return False

    # Patch version can be different
    return True


def load_schema(name, schema_dir="schemas", version=None):
    """Load schema with version information

    Args:
        name: Schema name (e.g., 'image', 'eeg')
        schema_dir: Base schemas directory
        version: Schema version to load (e.g., 'stable', 'v0.1', '0.1').
                 If None, uses DEFAULT_SCHEMA_VERSION
    """
    # Normalize version string
    if version is None:
        version = DEFAULT_SCHEMA_VERSION
    elif version and not version.startswith("v") and version != "stable":
        version = f"v{version}"

    # Build schema path with version
    schema_path = os.path.join(schema_dir, version, f"{name}.schema.json")

    if os.path.exists(schema_path):
        try:
            with open(schema_path) as f:
                schema = json.load(f)

            # Add schema metadata for versioning
            schema_version = schema.get("version", "1.0.0")
            schema["_validator_info"] = {
                "schema_version": schema_version,
                "modality": name,
                "version_tag": version,
                "loaded_at": json.dumps({"timestamp": "runtime"}),
            }
            return schema
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load schema {schema_path}: {e}")
    return None


def load_all_schemas(schema_dir="schemas", version=None):
    """Load all available schemas for a specific version

    Args:
        schema_dir: Base schemas directory
        version: Schema version to load (e.g., 'stable', 'v0.1', '0.1').
                 If None, uses DEFAULT_SCHEMA_VERSION
    """
    # Normalize version
    if version is None:
        version = DEFAULT_SCHEMA_VERSION
    elif version and not version.startswith("v") and version != "stable":
        version = f"v{version}"

    schemas = {}

    # Standard modalities
    modalities = [
        "survey",
        "biometrics",
        "events",
        "dataset_description",
    ]

    for modality in modalities:
        schema = load_schema(modality, schema_dir, version)
        if schema:
            schemas[modality] = schema

    # MRI nested schemas (if they exist)
    mri_modalities = ["anat", "func", "fmap", "dwi"]
    for modality in mri_modalities:
        mri_schema_path = os.path.join(
            schema_dir, version, "mri", f"{modality}.schema.json"
        )
        if os.path.exists(mri_schema_path):
            schemas[modality] = load_schema(
                os.path.join("mri", modality), schema_dir, version
            )

    return schemas


def get_available_schema_versions(schema_dir="schemas"):
    """Get list of available schema versions

    Returns:
        List of version strings (e.g., ['stable', 'v0.1'])
    """
    versions = []
    if os.path.exists(schema_dir):
        for item in os.listdir(schema_dir):
            item_path = os.path.join(schema_dir, item)
            if os.path.isdir(item_path) and (item == "stable" or item.startswith("v")):
                versions.append(item)
    return sorted(versions, key=lambda x: (x != "stable", x))


def validate_schema_version(metadata, schema):
    """Validate that metadata schema version is compatible with loaded schema"""
    issues = []

    if not schema or "_validator_info" not in schema:
        return issues

    schema_version = schema["_validator_info"]["schema_version"]

    # Check if metadata specifies a schema version
    metadata_version = None
    if "Metadata" in metadata and "SchemaVersion" in metadata["Metadata"]:
        metadata_version = metadata["Metadata"]["SchemaVersion"]

    if metadata_version:
        if not is_compatible_version(schema_version, metadata_version):
            issues.append(
                (
                    "WARNING",
                    f"Schema version mismatch: metadata uses v{metadata_version}, "
                    f"validator expects v{schema_version}. Consider upgrading metadata.",
                )
            )

    return issues
