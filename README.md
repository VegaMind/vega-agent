# Vega — A personal AI agent with cross-session memory and privacy built in

Your personal AI agent that lives on your machine. Private by default, extensible by design, and ready in one command.

[![GitHub Stars](https://img.shields.io/github/stars/VegaMind/vega-agent?style=flat-square&logo=github)](https://github.com/VegaMind/vega-agent)
[![Release](https://img.shields.io/github/v/release/VegaMind/vega-agent?style=flat-square&logo=github)](https://github.com/VegaMind/vega-agent/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/VegaMind/vega-agent/ci.yml?style=flat-square&logo=github-actions&label=tests)](https://github.com/VegaMind/vega-agent/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square&logo=python)](https://python.org)
[![Docs](https://img.shields.io/badge/docs-github.io-blue?style=flat-square&logo=readthedocs)](https://VegaMind.github.io/vega-agent)
[![Discord](https://img.shields.io/badge/discord-join-5865F2?style=flat-square&logo=discord)](https://discord.gg/vega-agent)

---

## One Command

```bash
curl -fsSL https://getvega.sh | bash
```

That's it. The installer detects your OS, resolves the latest release, and sets up a fully isolated environment under `~/.vega/` — no global Python package pollution, no root access needed.

Need more control? Flags are available:

```bash
curl -fsSL https://getvega.sh | bash -s -- --version v0.1.0 --path /opt/vega --yes
```

---

## What is Vega?

**Vega** (named after the brightest star in the constellation Lyra — from the Arabic *wāqi'*, meaning "falling" or "landing") is a personal AI agent you install on your own machine.

Vega is not a cloud service, not a chatbot website, and not another SaaS subscription. It is a local-first CLI agent with persistent memory, a structured knowledge graph (the Context Tree), transparent audit logging, and a clean, extensible architecture built on LangGraph workflows.

Whether you use it as a daily assistant, a research companion, a thinking tool, or a knowledge base, Vega keeps your data where it belongs — with you.

---

## Quick Start

1. **Install**
   ```bash
   curl -fsSL https://getvega.sh | bash
   ```

2. **Initialise**
   ```bash
   vega init
   ```
   The setup wizard walks you through API key configuration, model provider selection, and privacy toggles. Pass `--auto` to skip all prompts.

3. **Ask a question**
   ```bash
   vega ask "What can you do?"
   ```

4. **Start the interactive shell**
   ```bash
   vega shell
   ```

5. **Check your status**
   ```bash
   vega status
   ```

6. **View the audit trail**
   ```bash
   vega audit
   ```

---

## Features

| Area | Feature | Description |
|------|---------|-------------|
| 🧠 | **Long-term memory** | ChromaDB-powered semantic recall with two collections: memories (facts, notes, observations) and episodic (recent interactions). |
| 🌳 | **Context Tree** | A SQLite-based knowledge graph that replaces flat note-taking. Nodes with typed relationships (depends on, references, contradicts, extends), importance scoring, automatic pruning, and branch condensation. |
| 🔐 | **Privacy gateway** | Every tool call and LLM invocation routes through a scope-enforcing gateway that blocks local-scoped data from reaching external APIs — before the data ever leaves. |
| 📋 | **Transparent audit log** | Every action is recorded as human-readable JSONL under `~/.vega/audit/`. One file per day. Never automatically deleted. You own every entry. |
| 🏷️ | **Data boundary types** | Every piece of user data carries a scope tag — `local`, `context_for_llm`, or `shareable` — and the gateway enforces those scopes at runtime. |
| 🔑 | **Optional encryption** | Convenience helpers for encrypting local data at rest via Fernet symmetric encryption. |
| 📝 | **Obsidian import** | Migrate an entire Obsidian vault into the Context Tree — folder hierarchy becomes branch/leaf structure, wiki-links become typed edges, frontmatter metadata becomes importance scores and tags. |
| 🛠️ | **Extensible tools** | A plugin-like tool system built on LangGraph. Add custom tools, define new workflows, and extend Vega without forking. |
| 💬 | **Multi-model** | Works with OpenRouter, OpenAI, or any compatible API. Configure provider and model per session or override at the command line. |
| 👤 | **Shell history** | Full conversation persistence within sessions. Commands: `/clear` to reset context, `/help` for shell commands, `/exit` to quit. |

---

## Privacy

Vega's privacy model is simple, transparent, and honest about what it does and doesn't do.

**Local-first by default.** All data — memory vectors, context tree nodes, audit logs, configuration — lives under `~/.vega/` on your machine. Nothing is sent anywhere unless you configure an API key and explicitly ask the agent a question.

**Transparent audit logging.** Every action Vega takes — every tool call, every LLM invocation, every file access — is recorded as a structured JSONL entry in `~/.vega/audit/`. You can review the entire history with `vega audit` at any time. The audit log is append-only and never automatically pruned.

**Scope enforcement.** Data is tagged with one of three scopes:
- `local` — must never leave this machine (passwords, API keys, personal notes)
- `context_for_llm` — may be sent to a local LLM but not to any external API
- `shareable` — may be sent to external APIs (still audited)

The gateway checks every outbound call against the data's scope tag. A `local`-scoped piece of data reaching an external API is blocked before transmission, and the block is itself recorded in the audit trail.

**Does Vega use homomorphic encryption or zero-knowledge proofs?** No. Privacy engineering is about tradeoffs, and Vega optimises for transparency and practical safety over cryptographic provability. If you need formal privacy guarantees, Vega's architecture makes it straightforward to add an encryption layer on top. See the comparison table below for how this compares to other projects.

---

## Architecture

Vega is composed of several loosely coupled subsystems, each in its own module under `src/vega/`:

```
src/vega/
├── __init__.py          Package metadata (version, author)
├── __main__.py          Entry point for `python -m vega`
├── cli.py               CLI interface (click + rich)
├── config.py            YAML configuration loader/validator
├── gateway.py           Tool routing + scope enforcement + audit logging
├── memory/              ChromaDB vector store (memories + episodic)
│   ├── __init__.py
│   └── vector.py
├── context_tree/        SQLite knowledge graph
│   ├── __init__.py
│   ├── node.py          Node, Edge, BranchSummaryStats dataclasses
│   ├── db.py            SQLite schema + CRUD
│   ├── pruning.py       Archiving, decay, condensation
│   └── migration.py     Obsidian vault import
└── privacy/             Privacy layer
    ├── __init__.py
    ├── audit.py         JSONL audit log manager
    ├── boundary.py      UserData/AgentOutput scope types
    └── encrypt.py       Optional Fernet encryption helpers
```

**CLI** (`cli.py`) — The user-facing interface built with Click and Rich. Commands include `init`, `ask`, `shell`, `status`, `audit`, `privacy`, `encrypt`, and `migrate`.

**Config** (`config.py`) — YAML-based configuration stored at `~/.vega/config.yaml`. Four sections: `privacy`, `model`, `paths`, `features`. Validated on load with sensible defaults.

**Gateway** (`gateway.py`) — The central routing layer. Every outbound call passes through `route_tool_call()` or `route_llm_call()`, which check data scope, block violations, and log everything to the audit trail.

**Memory** (`memory/vector.py`) — Wraps ChromaDB's persistent client with two default collections: `vega_memories` (long-term semantic recall) and `vega_episodic` (recent interactions). Supports store, search, delete, and collection management.

**Context Tree** (`context_tree/`) — A hierarchical knowledge graph stored in SQLite. Nodes have types (root, branch, leaf), importance scores (decayed over time), TTLs, tags, and typed relationships (depends_on, references, contradicts, extends). Automatic maintenance runs decay, archival, and condensation.

**Privacy** (`privacy/`) — Three layers: audit (JSONL logging), boundary (scope-tagged data types), and encryption (Fernet helpers for local data at rest).

---

## Context Tree

The Context Tree is Vega's answer to the question: *"How do you give an AI agent persistent, structured knowledge without drowning it in raw text?"*

Most AI assistants treat context as a flat conversation history — a list of messages that grows linearly and forgets everything between sessions. The Context Tree replaces that with a structured knowledge graph that the agent actively maintains.

**Nodes** are the basic unit. Each node has a title, content (markdown), an importance score (0.0–1.0), access tracking, optional TTL, tags, and a source annotation. Nodes are typed:
- **Root** — identity/persona nodes (who the agent is, who the user is)
- **Branch** — organising category or topic
- **Leaf** — a specific fact, note, observation, or memory

**Edges** connect nodes with typed relationships:
- `depends_on` — one concept builds on another
- `references` — related but not dependent
- `contradicts` — conflicting information (important for belief updates)
- `extends` — a refinement or elaboration

**Automatic maintenance** keeps the tree from growing indefinitely:
- **Importance decay** — every node's importance decreases by 5% per week. Frequently accessed nodes get reinforced (importance +10% on access).
- **Archiving** — nodes below an importance threshold and unused for 30+ days are archived (not deleted — just hidden from active queries).
- **Branch condensation** — when a branch accumulates more than 50 leaves, they are merged into a single condensed leaf (optionally summarised via an LLM call).

**Obsidian migration** (`vega migrate /path/to/vault`) — imports an entire Obsidian vault into the Context Tree. Folder structure becomes branch hierarchy. Markdown files become leaves. Wiki-links (`[[link]]`) become edges. Frontmatter metadata (importance, weight, priority, rating) becomes node importance. Tags are preserved.

The result is a knowledge base that grows with you, forgets what you don't need, and organises itself without manual folder management.

---

## Comparison

| | Vega | Hermes Agent | OpenHuman | Kai |
|---|---|---|---|---|
| **Focus** | Personal AI agent, local-first | General-purpose AI agent | Privacy-preserving AI | Chatbot platform |
| **Installation** | One-command installer | Python package | Docker / cloud | SaaS |
| **Privacy model** | Scope enforcement + audit log | Configurable | Homomorphic encryption | Cloud-only |
| **Memory** | ChromaDB vector store + Context Tree | Variable | Encrypted vector store | Session-only |
| **Knowledge graph** | SQLite Context Tree with pruning | Optional | None | None |
| **Audit trail** | Built-in JSONL logging | Configurable | Built-in | None |
| **Obsidian import** | Built-in migration | None | None | None |
| **Extensibility** | LangGraph workflows | Plugin system | Protocol-based | API-only |
| **Model support** | OpenRouter, OpenAI, local | Multiple providers | Custom protocol | Proprietary |
| **Local-only mode** | Yes (`local_models_only`) | Partial | Yes | No |

Vega sits in a specific niche: a local-first personal AI agent that prioritises transparent privacy, persistent structured memory, and clean extensibility — without sacrificing ease of use.

---

## LangGraph Workflows

Vega's tool system and agent loop are built on **LangGraph**, making it straightforward to add custom workflows without modifying core code.

The architecture supports:
- **Conditional branching** — route between tools based on LLM output
- **Human-in-the-loop** — pause execution for user confirmation before destructive actions
- **Parallel execution** — run multiple tool calls concurrently where safe
- **State persistence** — carry context across workflow steps via a shared state dict
- **Checkpointing** — save and resume long-running workflows

To add a custom workflow, create a Python file in `~/.vega/workflows/` that exports a LangGraph `StateGraph`:

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class MyState(TypedDict):
    input: str
    output: str

def run_my_tool(state: MyState) -> MyState:
    # Your tool logic here
    return {"output": f"Processed: {state['input']}"}

graph = StateGraph(MyState)
graph.add_node("tool", run_my_tool)
graph.set_entry_point("tool")
graph.add_edge("tool", END)
app = graph.compile()
```

Vega discovers and registers workflows automatically on startup.

---

## Development

### Clone and set up

```bash
git clone https://github.com/VegaMind/vega-agent.git
cd vega

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

Tests cover:
- CLI commands (`test_cli.py`)
- Configuration loading and validation (`test_config.py`)
- Memory store operations (`test_memory.py`)
- Context Tree CRUD, pruning, and migration (`test_context_tree.py`)
- Privacy gateway, audit logging, and boundary enforcement (`test_privacy.py`)

### Code style

Vega follows PEP 8 with a 100-character line limit. The codebase uses Python 3.11+ features throughout — `from __future__ import annotations`, `list[str]` syntax, dataclasses, and structural pattern matching where appropriate.

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Commit your changes with clear, descriptive messages
4. Push to your fork and open a pull request

All contributions are welcome — bug fixes, documentation improvements, new tools, workflow examples, and translation efforts.

---

## Roadmap

### v0.1 — Foundation *(current)*
- [x] One-command installer
- [x] CLI interface (`init`, `ask`, `shell`, `status`, `audit`)
- [x] YAML configuration with validation
- [x] ChromaDB memory store (semantic + episodic collections)
- [x] Context Tree graph (SQLite: nodes, edges, types, CRUD)
- [x] Privacy gateway (scope enforcement + audit logging)
- [x] Data boundary types (`UserData`, `AgentOutput`)
- [x] Optional Fernet encryption
- [x] Obsidian vault migration

### v0.2 — Workflows & Tools
- [ ] LangGraph workflow registry
- [ ] Built-in tool suite (web search, file read/write, code evaluation)
- [ ] Human-in-the-loop confirmation prompts
- [ ] Plugin discovery from `~/.vega/workflows/`
- [ ] Shell `/stats` command (token usage, rate limits)

### v0.3 — Memory Enhancement
- [ ] Episodic memory summarization (nightly rollups)
- [ ] Cross-session context stitching
- [ ] Memory importance reinforcement from user feedback
- [ ] Full-text search across all data stores
- [ ] Context Tree visualisation (`vega tree`)

### v0.4 — Multi-Agent & Collaboration
- [ ] Agent-to-agent message passing
- [ ] Shared context trees across sessions
- [ ] MCP (Model Context Protocol) server mode
- [ ] REST API for integration with external tools

### v0.5 — Quality of Life
- [ ] Tab completion for shell commands
- [ ] Configuration profiles (work, personal, research)
- [ ] Automatic backup of context tree + memory to local archive
- [ ] Performance benchmarks and optimisation guide
- [ ] Comprehensive documentation site

---

## License

Vega is released under the **MIT License**. See [LICENSE](LICENSE) for the full text.

---

## Acknowledgments

Vega builds on the work of several outstanding open-source projects:

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** — the architectural inspiration and the agent runtime that Vega extends with privacy-first design, persistent memory, and a structured knowledge graph.
- **[Fabric](https://github.com/danielmiessler/fabric)** — patterns for modular AI tooling and prompt management.
- **[ChromaDB](https://github.com/chroma-core/chroma)** — the embedded vector database that powers Vega's semantic memory.
- **[LangGraph](https://github.com/langchain-ai/langgraph)** — the workflow orchestration framework underlying Vega's tool system.
- **[Click](https://github.com/pallets/click)** — the CLI framework that makes Vega's command interface clean and extensible.
- **[Rich](https://github.com/Textualize/rich)** — terminal rendering for status displays, tables, and panels.
- **[OpenRouter](https://openrouter.ai)** — multi-provider API gateway for LLM access.

---

## Contributors

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<!-- This section is auto-generated. Add yourself via: `npx all-contributors-cli add` -->
<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

Vega is open to contributions from anyone. If you'd like to be listed here, open a pull request and we'll add you using the [All Contributors](https://allcontributors.org) bot.

---

<div align="center">
  <sub>Built with care by the Vega team. Your personal AI. Installed. Private.</sub>
</div>