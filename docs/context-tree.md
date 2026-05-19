# Context Tree

The Context Tree is Vega's knowledge management system. It replaces static file vaults (like Obsidian) with a self-maintaining, machine-readable knowledge graph.

## Why a tree?

Most AI agents have two problems:

1. **They forget everything between sessions** — no persistence
2. **They dump everything into context** — no prioritization

The Context Tree solves both. It stores knowledge in a structured SQLite database with importance scoring, automatic pruning, and semantic search via ChromaDB.

## Node types

| Type | Purpose | Lifespan | Example |
|------|---------|----------|---------|
| **Root** | Persistent identity | Permanent | User profile, constitution, capabilities |
| **Branch** | Projects and domains | Months | Trading system, VISORA, research topics |
| **Leaf** | Ephemeral memories | Days/weeks | Session logs, conversation summaries, notes |

## How it works

```
USER ASKS: "What were we doing with the trading system?"

1. Agent queries context tree for matching branch nodes
2. Loads most recent leaf children with highest importance
3. ChromaDB provides semantic recall on top
4. Response grounded in actual history
5. Access count increments, importance recalculates
```

## Automatic maintenance

| Feature | Behavior |
|---------|----------|
| **Importance decay** | Every node loses 5% importance per week unless accessed |
| **Auto-archiving** | Nodes with importance < 0.1 and untouched for 30 days get archived |
| **Branch condensation** | When a branch has 50+ leaves, Vega summarizes them into one condensed leaf |
| **Relationship inference** | Vega detects related content and creates edges between nodes |

## Edges

Nodes can be connected with typed relationships:

- `depends_on` — one node requires another
- `references` — one node mentions another
- `contradicts` — conflicting information
- `extends` — elaboration or continuation

## Obsidian migration

```bash
vega migrate --from-obsidian /path/to/vault
```

This walks your vault, creates branch nodes for directories, leaf nodes for markdown files, and converts `[[wiki-links]]` into edge relationships.