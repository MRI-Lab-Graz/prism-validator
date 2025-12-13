# Schema Versioning Guide

## Overview

Prism-Validator now supports schema versioning, similar to Docker image tagging. This allows you to validate datasets against different versions of the validation schemas.

## Available Versions

Schema versions are stored in the `schemas/` directory:

- **`stable/`** - The current stable version (default)
- **`v0.1/`** - Version 0.1 (initial release)

## Using Schema Versions

### Command Line

To specify a schema version when validating a dataset:

```bash
# Use stable version (default)
python prism-validator.py /path/to/dataset

# Use specific version
python prism-validator.py /path/to/dataset --schema-version 0.1
python prism-validator.py /path/to/dataset --schema-version v0.1
python prism-validator.py /path/to/dataset --schema-version stable
```

List available schema versions:

```bash
python prism-validator.py --list-versions
```

### Web Interface

1. Navigate to the web interface
2. Select the desired schema version from the dropdown menu
3. Upload your dataset or provide a local folder path
4. The validation results will show which schema version was used

## Version Naming Convention

- **`stable`** - Always points to the current recommended version
- **`v0.1`, `v0.2`, etc.** - Semantic versioning format
- Version numbers can be specified with or without the `v` prefix (e.g., `0.1` or `v0.1`)

## Creating New Schema Versions

To create a new schema version:

1. Create a new directory in `schemas/` (e.g., `schemas/v0.2/`)
2. Copy schema files from the previous version or create new ones
3. Modify the schemas as needed
4. Test the new version thoroughly before marking it as `stable`

```bash
# Create new version
mkdir schemas/v0.2
cp schemas/stable/*.json schemas/v0.2/

# After testing and validation, update stable
rm -rf schemas/stable
cp -r schemas/v0.2 schemas/stable
```

## Best Practices

1. **Always use `stable` for production validation** unless you have a specific reason to use an older version
2. **Version numbers should follow semantic versioning** (MAJOR.MINOR.PATCH)
3. **Document breaking changes** in schema versions
4. **Keep at least 2-3 previous versions** for backward compatibility
5. **Test new schemas thoroughly** before promoting to `stable`

## Migration Between Versions

If you need to migrate datasets validated with an older schema version:

1. Review the changes between schema versions
2. Update your dataset metadata if needed
3. Re-validate with the new schema version
4. Compare validation results to identify any new issues

## Schema Version in Reports

Validation reports (JSON and web interface) include the schema version used:

```text
{
  "schema_version": "stable",
  "validation_timestamp": "2025-10-09T...",
  "results": { ... }
}
```

This ensures you can always trace which schema version was used for validation.

## FAQ

**Q: What happens if I don't specify a version?**  
A: The system defaults to `stable`.

**Q: Can I validate with multiple versions at once?**  
A: No, you must run separate validations for each version you want to test.

**Q: What if a schema version doesn't exist?**  
A: The validator will fail with an error message indicating the version was not found.

**Q: How do I know which version to use?**  
A: Always use `stable` unless you're specifically testing compatibility with an older version or a development version.

## Version History

- **v0.1** (2025-10-09) - Initial schema versioning implementation
- **stable** - Current recommended version

## Related Documentation

- [Schema Documentation](SCHEMA_VERSIONING.md)
- [Quick Start Guide](QUICK_START.md)
- [Implementation Details](IMPLEMENTATION_SUMMARY.md)
