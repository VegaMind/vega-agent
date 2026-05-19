# Privacy Model

Vega is designed to be **private by default, transparent always.**

## Core principle

> Your data stays on your machine. Vega never phones home.

No telemetry. No analytics. No background network calls. Vega communicates only with the LLM APIs you explicitly configure.

## The approach

We don't try to mathematically prove privacy (like OpenHuman's 4-layer cryptographic boundary). Instead, we make privacy **obvious and auditable.** You can always see exactly what Vega has done, what data it has, and where it's been sent.

## Layers

### 1. Local-first by default

```
~/.vega/
├── config.yaml        # Your configuration
├── data/              # All local data
├── context_tree.db    # Knowledge graph (SQLite)
├── audit/             # Action logs (JSONL)
├── models/            # Local model files (optional)
└── logs/              # Runtime logs
```

Zero network connections on first install. LLM API calls require explicit configuration.

### 2. Transparent audit log

Every action is logged to `~/.vega/audit/YYYY-MM-DD.jsonl`:

```bash
vega audit
```

Shows you: what happened, when, why, what data was involved, which model was used.

### 3. Data scope enforcement

Data is tagged with a scope:

| Scope | Meaning | Can be sent to LLM? |
|-------|---------|---------------------|
| `local` | Sensitive personal data | ❌ Blocked by gateway |
| `context_for_llm` | Context needed for reasoning | ✅ Allowed |
| `shareable` | Intended for sharing | ✅ Allowed |

The gateway enforces these at the code level — not just as a policy.

### 4. Optional encryption

```bash
vega encrypt --setup
```

Generates a local encryption key. All stored data is encrypted with AES-256 (Fernet). Fully optional — your choice.

## What we don't claim

- **No cryptographic proofs** — we don't use TEEs, attestation quotes, or zero-knowledge proofs. That level of verification is infrastructure-heavy and unnecessary for most users.
- **No homomorphic encryption** — your data is decrypted when Vega uses it. That's true of every local AI agent.
- **No external audit service** — no Guild.ai, no third-party verifier. The audit log is local and transparent.

## What we do claim

- **You can always see what Vega did** — `vega audit` shows everything
- **You control what leaves your machine** — `vega privacy` shows your current data boundaries
- **No telemetry, no analytics, no tracking** — check the code, it's MIT open source