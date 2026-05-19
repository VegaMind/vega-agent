# Contributing

We love contributions! Vega is MIT open source and we welcome everyone.

## Code of Conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/). By participating, you agree to uphold it.

## Getting started

```bash
git clone https://github.com/VegaMind/vega-agent
cd vega
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/ -v
```

We aim for 90%+ coverage on all new code.

## Code style

- Python 3.11+
- Ruff linting (`ruff check src/ tests/`)
- Type hints on all public functions
- Docstrings on all modules and public APIs

## Pull request process

1. Open an issue describing what you want to change
2. Fork the repo and create a branch
3. Write tests first (TDD)
4. Implement the change
5. Run tests and lint
6. Submit a PR with a clear description

## Project structure

```
src/vega/
├── cli.py              # CLI commands (click)
├── config.py           # YAML configuration
├── gateway.py          # Tool routing + audit
├── engine.py           # Core agent loop
├── context_tree/       # Knowledge management
├── memory/             # ChromaDB vector storage
├── privacy/            # Audit + boundary types
├── model/              # LLM routing
├── tools/              # Tool registry
├── skills/             # Skill system
└── workflows/          # LangGraph workflows
```

## Need help?

Open a [Discussion](https://github.com/VegaMind/vega-agent/discussions) or join our [Discord](https://discord.gg/vega-agent).