# LangGraph Workflows

Vega is built for extensibility. Add new capabilities through **LangGraph workflows** — directed graphs of agent behavior.

## Why LangGraph?

LangGraph lets you define precise, multi-step agent behaviors as state machines. Unlike simple prompt chains, LangGraph workflows can:

- Branch based on conditions
- Loop until a condition is met
- Track state across steps
- Use tools at specific points in the flow
- Be composed together

## Architecture

```
            ┌─────────────────────────────┐
            │         WORKFLOW ENGINE      │
            │                              │
            │  observe → reason → act      │
            │     ↑                │       │
            │     └── reflect ←────┘       │
            │                              │
            │  Each step is a LangGraph     │
            │  node with state management   │
            └──────────────────────────────┘
```

## Built-in workflows

| Workflow | Status | Description |
|----------|--------|-------------|
| **Observe** | Coming in v0.3 | Check context tree, recall memories → reason → act |
| **Learn** | Coming in v0.4 | Capture feedback, identify patterns, store insights |
| **Reflect** | Coming in v0.5 | Periodically scan history, update self-model |
| **Curiosity** | Coming in v1.0 | Proactive exploration during idle time |

## Custom workflows

```python
from langgraph.graph import StateGraph, State
from typing import TypedDict, Literal

class AgentState(TypedDict):
    input: str
    context: list
    output: str

workflow = StateGraph(AgentState)

def observe(state: AgentState) -> dict:
    # Check context tree for relevant history
    return {"context": ["relevant memories"]}

def reason(state: AgentState) -> dict:
    # Route to LLM with context
    response = llm_call(state["input"], context=state["context"])
    return {"output": response}

workflow.add_node("observe", observe)
workflow.add_node("reason", reason)
workflow.add_edge("observe", "reason")
workflow.set_entry_point("observe")

app = workflow.compile()
result = app.invoke({"input": "user question", "context": []})
```

## ASI trajectory

LangGraph workflows are the building blocks toward Domain ASI:

| Phase | Capability | Workflow pattern |
|-------|-----------|-----------------|
| v0.1 | Basic Q&A | Single LLM call |
| v0.3 | Context-aware | Observe → Reason → Act → Reflect |
| v0.4 | Self-improving | + Learn from mistakes |
| v0.5 | Meta-cognitive | + Self-model + Periodic reflection |
| v1.0+ | Proactive | + Curiosity-driven exploration |