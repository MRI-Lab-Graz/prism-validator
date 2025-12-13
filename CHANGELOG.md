# Changelog

All notable changes to the Prism-Validator project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-10-09

### Added - Major Release 🎉

This is the first major release of Prism-Validator with comprehensive features for validating psychological research datasets.

#### Schema Versioning System
- **Docker-like schema versioning** (`stable`, `v0.1`, etc.)
- `--schema-version` CLI flag to specify validation schema version
- `--list-versions` command to display available schema versions
- Schema version selector in web interface (dropdown menu)
- Version information included in all validation results
- Automatic version normalization (supports both `0.1` and `v0.1` formats)
- Default to `stable` version when not specified
- Comprehensive documentation for schema versioning

#### Web Interface Improvements
- Schema version dropdown in upload form
- Schema version selector for local folder validation
- Updated results page to display schema version used
- Improved logo display with correct aspect ratio
- Enhanced user experience with clear version selection

#### Core Features
- Multi-modal validation support (image, movie, audio, EEG, eye-tracking, behavior, physiological)
- BIDS-inspired filename validation
- JSON schema validation for metadata files
- Cross-subject consistency checking
- Comprehensive validation reports
- Support for session-based and direct subject organization
- Local folder validation (no upload required)
- DataLad-style upload (metadata only, placeholders for large files)

#### Documentation
- Added `SCHEMA_VERSIONING_GUIDE.md` - Complete user guide
- Added `SCHEMA_VERSIONING_IMPLEMENTATION.md` - Technical details
- Added `SCHEMA_VERSIONING_QUICKREF.md` - Quick reference
- Added `SCHEMA_VERSIONING_COMPLETE.md` - Implementation summary
- Added `SCHEMA_VERSIONING_CHECKLIST.md` - Development checklist
- Added `SCHEMA_VERSIONING_VISUAL.md` - Visual documentation
- Updated README.md with versioning information

#### Infrastructure
- Created `schemas/stable/` directory for stable schema version
- Created `schemas/v0.1/` directory for version 0.1
- Enhanced `schema_manager.py` with version-aware loading
- Updated `runner.py` to support schema version parameter
- Improved web interface validation workflow

### Changed
- Updated main validator to accept `schema_version` parameter
- Modified web interface to pass schema version through validation pipeline
- Enhanced templates with schema version UI elements
- Updated README with new features and examples

### Technical Details
- Python 3.10+ compatible
- Flask-based web interface
- JSON Schema validation
- Cross-platform support (Windows, macOS, Linux)
- Zero-dependency validation core

### Migration Guide
For existing users:
- No breaking changes - all existing code continues to work
- Default behavior uses `stable` schema version
- Explicitly specify version only if needed for specific use cases
- See `docs/SCHEMA_VERSIONING_GUIDE.md` for detailed migration instructions

---

## Release Notes

### v1.0.0 Highlights

🎉 **First Major Release** - Prism-Validator is now production-ready!

**Key Features:**
- ✅ Schema versioning system (Docker-like)
- ✅ Web interface with schema selection
- ✅ Command-line tools with version support
- ✅ Comprehensive validation for psychological datasets
- ✅ Complete documentation suite

**What's Next:**
- Schema diff utilities
- Auto-migration tools
- Enhanced modality support
- CI/CD integration examples

### Acknowledgments
- Developed at **MRI-Lab Graz**, University of Graz
- Maintained by **Karl Koschutnig**
- Built for the research community ❤️

### Links
- [GitHub Repository](https://github.com/MRI-Lab-Graz/prism-validator)
- [Documentation](https://github.com/MRI-Lab-Graz/prism-validator/tree/main/docs)
- [Schema Versioning Guide](https://github.com/MRI-Lab-Graz/prism-validator/blob/main/docs/SCHEMA_VERSIONING_GUIDE.md)

---

[1.0.0]: https://github.com/MRI-Lab-Graz/prism-validator/releases/tag/v1.0.0

## [1.3.0] - 2025-11-28

### Changed
- **Project Rename**: Renamed project from `psycho-validator` to `prism-validator`.
- **Repository Restructuring**: Moved helper scripts to `helpers/` directory.
- **Documentation**: Updated all documentation to reflect the new name.
