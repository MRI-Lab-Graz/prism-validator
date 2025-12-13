# Creating GitHub Release v1.0.0 - Step-by-Step Guide

## Prerequisites
- [ ] All changes committed to git
- [ ] Tests passing
- [ ] Documentation complete
- [ ] CHANGELOG.md created
- [ ] Version numbers updated

## Step 1: Commit All Changes

```bash
cd /Users/karl/work/github/prism-validator

# Add all new files
git add schemas/stable/
git add schemas/v0.1/
git add docs/SCHEMA_VERSIONING*.md
git add static/img/MRI_Lab_Logo.png
git add CHANGELOG.md
git add RELEASE_NOTES_v1.0.0.md

# Add modified files
git add README.md
git add prism-validator.py
git add src/schema_manager.py
git add src/runner.py
git add web_interface.py
git add templates/base.html
git add templates/index.html
git add templates/results.html

# Commit with descriptive message
git commit -m "Release v1.0.0: Schema versioning system and major improvements

- Add Docker-like schema versioning (stable, v0.1)
- Add --schema-version CLI flag
- Add schema version selector to web interface
- Add comprehensive documentation suite
- Improve logo display in web interface
- Update README with new features
- Add CHANGELOG and release notes

This is the first major release with production-ready features."

# Push to GitHub
git push origin main
```

## Step 2: Create Git Tag

```bash
# Create annotated tag
git tag -a v1.0.0 -m "Release v1.0.0: First Major Release

🎉 Major Features:
- Schema versioning system (Docker-like)
- Enhanced web interface with version selection
- Comprehensive validation for psychological datasets
- Complete documentation suite

See CHANGELOG.md for full details."

# Push tag to GitHub
git push origin v1.0.0
```

## Step 3: Create GitHub Release

### Option A: Using GitHub Web Interface (Recommended)

1. **Navigate to your repository**
   - Go to: https://github.com/MRI-Lab-Graz/prism-validator

2. **Click on "Releases"**
   - Located in the right sidebar or under "Code" tab

3. **Click "Draft a new release"**

4. **Fill in Release Information:**

   **Tag version:** `v1.0.0` (select existing tag)
   
   **Release title:** `v1.0.0 - First Major Release 🎉`
   
   **Description:** (Copy from RELEASE_NOTES_v1.0.0.md or use this):

   ```markdown
   # Prism-Validator v1.0.0 - First Major Release 🎉

   We're excited to announce the first major release of **Prism-Validator**!

   ## 🌟 Highlights

   ### Schema Versioning System
   - ✅ Docker-like versioning (`stable`, `v0.1`, etc.)
   - ✅ CLI flag: `--schema-version`
   - ✅ Web interface dropdown selector
   - ✅ Version tracking in results

   ### Features
   - ✅ Multi-modal validation (image, movie, audio, EEG, eye-tracking, behavior, physiological)
   - ✅ BIDS-inspired validation
   - ✅ Web interface & CLI
   - ✅ Complete documentation

   ## 📦 Quick Start

   ```bash
   git clone https://github.com/MRI-Lab-Graz/prism-validator.git
   cd prism-validator
   ./setup.sh
   python launch_web.py
   ```

   ## 📚 Documentation
   - [Quick Start Guide](QUICK_START.md)
   - [Schema Versioning Guide](SCHEMA_VERSIONING_GUIDE.md)
   - [Full Changelog](CHANGELOG.md)

   ## 🔗 Links
   - [Full Release Notes](RELEASE_NOTES_v1.0.0.md)
   - [Documentation](index.rst)

   **Version**: 1.0.0  
   **Release Date**: October 9, 2025  
   **Status**: Production Ready ✅
   ```

5. **Set as latest release:** ✅ Check "Set as the latest release"

6. **Click "Publish release"**

### Option B: Using GitHub CLI (gh)

```bash
# Install GitHub CLI if needed
# brew install gh  # macOS
# See: https://cli.github.com/

# Authenticate
gh auth login

# Create release
gh release create v1.0.0 \
  --title "v1.0.0 - First Major Release 🎉" \
  --notes-file RELEASE_NOTES_v1.0.0.md \
  --latest

# Or with inline notes
gh release create v1.0.0 \
  --title "v1.0.0 - First Major Release 🎉" \
  --notes "See CHANGELOG.md and RELEASE_NOTES_v1.0.0.md for details." \
  --latest
```

## Step 4: Verify Release

1. **Check release page:**
   - https://github.com/MRI-Lab-Graz/prism-validator/releases/tag/v1.0.0

2. **Verify:**
   - [ ] Release shows correct version (v1.0.0)
   - [ ] Title is correct
   - [ ] Description is formatted properly
   - [ ] Tag is linked correctly
   - [ ] Marked as "Latest release"
   - [ ] Release date is correct

3. **Test download:**
   ```bash
   # Test that release can be downloaded
   curl -L https://github.com/MRI-Lab-Graz/prism-validator/archive/refs/tags/v1.0.0.tar.gz -o test.tar.gz
   tar -tzf test.tar.gz | head
   rm test.tar.gz
   ```

## Step 5: Post-Release Tasks

### Update Documentation Links

If needed, update any documentation that references the repository:

```bash
# Check for any hardcoded version numbers
grep -r "0\." docs/
grep -r "beta" docs/
```

### Announce the Release

1. **Update README badges** (if you have any):
   - Version badge
   - Release badge
   - License badge

2. **Announce on:**
   - Lab website
   - Mailing lists
   - Social media
   - Relevant forums

3. **Create announcement template:**

   ```markdown
   🎉 Prism-Validator v1.0.0 Released!

   We're excited to announce the first major release of Prism-Validator,
   a BIDS-inspired validation tool for psychological research datasets.

   New features:
   - Schema versioning system
   - Enhanced web interface
   - Comprehensive documentation

   Download: https://github.com/MRI-Lab-Graz/prism-validator/releases/tag/v1.0.0
   Docs: https://github.com/MRI-Lab-Graz/prism-validator/tree/main/docs

   #OpenScience #ResearchTools #DataValidation
   ```

### Monitor and Support

- [ ] Watch for issues on GitHub
- [ ] Respond to questions
- [ ] Monitor usage
- [ ] Gather feedback

## Troubleshooting

### If Tag Already Exists
```bash
# Delete local tag
git tag -d v1.0.0

# Delete remote tag
git push origin --delete v1.0.0

# Recreate tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### If Release Needs Update
1. Go to release page on GitHub
2. Click "Edit release"
3. Make changes
4. Click "Update release"

### If You Need to Undo
```bash
# Delete release (via GitHub web interface or gh CLI)
gh release delete v1.0.0

# Delete tag
git tag -d v1.0.0
git push origin --delete v1.0.0
```

## Quick Command Summary

```bash
# Complete release workflow
cd /Users/karl/work/github/prism-validator

# 1. Commit everything
git add .
git commit -m "Release v1.0.0: First major release"
git push origin main

# 2. Create and push tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# 3. Create release on GitHub (web interface or gh CLI)
gh release create v1.0.0 \
  --title "v1.0.0 - First Major Release 🎉" \
  --notes-file RELEASE_NOTES_v1.0.0.md \
  --latest

# 4. Verify
git tag -l
git log --oneline -5
```

## Checklist

### Pre-Release
- [ ] All tests passing
- [ ] Documentation updated
- [ ] CHANGELOG.md created
- [ ] RELEASE_NOTES created
- [ ] Version numbers correct
- [ ] All files committed

### Release
- [ ] Changes committed to main
- [ ] Git tag created (v1.0.0)
- [ ] Tag pushed to GitHub
- [ ] GitHub release created
- [ ] Release notes added
- [ ] Marked as latest release

### Post-Release
- [ ] Release verified
- [ ] Download tested
- [ ] Documentation links work
- [ ] Announcement prepared
- [ ] Team notified

## Next Steps

After v1.0.0 is released:

1. **Start planning v1.1.0**
   - Gather feedback
   - Plan new features
   - Update roadmap

2. **Maintain v1.0.x**
   - Bug fixes as needed
   - Security updates
   - Documentation improvements

3. **Future versions**
   - v1.1.0 - Minor features
   - v1.2.0 - Additional modalities
   - v2.0.0 - Breaking changes (if needed)

---

**Remember**: Always test locally before creating a release!
