# Read the Docs (RTD)

This project uses Sphinx (with the Read the Docs theme) and builds documentation from the `docs/` folder.

## What RTD builds

- **Sphinx config**: `docs/conf.py`
- **Start page**: `docs/index.rst`
- **Markdown support**: MyST (`myst_parser`) is enabled, so `*.md` pages can be included in the Sphinx toctree.

## Local build

From the repo root (after running the setup script and activating `.venv`):

```bash
source .venv/bin/activate
cd docs
make html
```

Output is written to `docs/_build/html`.

## RTD configuration

Read the Docs is configured via `.readthedocs.yaml` in the repository root.

Key points:
- Uses `docs/conf.py` as the Sphinx configuration.
- Installs Python dependencies from `requirements.txt`.

If RTD builds fail, the first things to check are:
- Broken links in `docs/index.rst` (missing files referenced by the toctree).
- Dependency installation problems (wheel availability on RTD).
