# Installation

## One-liner (recommended)

```bash
curl -fsSL https://getvega.sh | bash
```

This works on **Linux** and **macOS**. Windows support coming soon.

### What it does

1. Detects your OS and architecture
2. Checks Python 3.11+ and git are installed
3. Creates `~/.vega/` with all required directories
4. Sets up a Python virtual environment
5. Installs Vega and all dependencies
6. Adds `vega` to your PATH
7. Runs interactive first-time setup

### Options

```bash
# Specify install directory
VEGA_HOME=~/.config/vega curl -fsSL https://getvega.sh | bash

# Install specific version
VEGA_VERSION=0.1.0 curl -fsSL https://getvega.sh | bash
```

## Via pip

```bash
pip install vega-agent
vega init
```

## From source

```bash
git clone https://github.com/vega-agent/vega
cd vega
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
vega init
```

## Requirements

- **Python 3.11+**
- **git**
- **macOS** or **Linux**
- ~500 MB disk space (for dependencies + ChromaDB)

## After install

```bash
vega ask "What can you do?"
vega status
vega audit
```