# Quick Start

## 1. Install

```bash
curl -fsSL https://getvega.sh | bash
```

## 2. Ask a question

```bash
vega ask "What's the current time in Tokyo?"
```

Vega routes your question through your configured model, checks the context tree for relevant history, and returns a response.

## 3. Start an interactive session

```bash
vega shell
```

Type your questions directly. Use `/help` for commands, `/exit` to quit.

## 4. Check your data

```bash
vega status
vega audit
vega privacy
```

## 5. Import from Obsidian

If you use Obsidian, import your vault:

```bash
vega migrate --from-obsidian ~/my-obsidian-vault
```

## 6. Configure

```bash
vega init
```

Re-run init anytime to change your model, privacy settings, or paths.

## What's next?

- Learn about the [Context Tree](context-tree.md) — how Vega remembers
- Read the [Privacy Model](privacy.md) — what stays local
- Build a [LangGraph Workflow](workflows.md) — extend Vega's capabilities