# Quick Start

## 1) Install (source checkout)

- macOS / Linux: follow [INSTALLATION.md](INSTALLATION.md) (uses `./setup.sh` and enforces a local `.venv`).
- Windows: follow [WINDOWS_SETUP.md](WINDOWS_SETUP.md).

## 2) Validate a dataset (CLI)

```bash
python prism-validator.py /path/to/dataset
```

See [USAGE.md](USAGE.md) for CLI options (including optional BIDS validation).

## 3) Run the web interface

```bash
python prism-validator-web.py
```

## 4) Use PRISM tools

```bash
python prism_tools.py --help
```

See [PRISM_TOOLS.rst](PRISM_TOOLS.rst).
