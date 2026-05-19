# Changelog

All notable changes to Vega will be documented in this file.

## [0.1.0] - 2026-05-19

### Added
- Initial release
- CLI interface: `vega init`, `vega ask`, `vega shell`, `vega status`, `vega audit`, `vega privacy`, `vega migrate`
- Context Tree: SQLite-backed knowledge graph with auto-pruning, importance decay, and branch condensation
- Privacy Layer: transparent JSONL audit log, data scope enforcement, optional encryption
- Memory: ChromaDB vector storage with semantic search
- Model routing: OpenRouter integration for multi-model support
- Install script: `curl -fsSL https://getvega.sh | bash`
- Documentation: installation, quick start, privacy model, context tree, workflow guide