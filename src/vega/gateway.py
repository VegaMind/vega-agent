"""Vega Gateway -- Tool routing with audit logging and data-scope enforcement.

Every tool call, LLM invocation, or external API request **must** route
through this module so that:

1. The action is logged to the audit trail.
2. The data scope (local / context_for_llm / shareable) is checked.
3. Any attempt to send local-scoped data to an external API is blocked.
4. The result is returned with an audit_id for traceability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from vega.privacy import audit as _audit
from vega.privacy.boundary import (
    SCOPE_CONTEXT_FOR_LLM,
    SCOPE_LOCAL,
    SCOPE_SHAREABLE,
    UserData,
)

# Known external / local targets
EXTERNAL_TARGETS: List[str] = [
    "openai-chat",
    "anthropic-chat",
    "openrouter-chat",
    "google-vertex",
    "groq-chat",
    "together-chat",
    "cloud-embed",
    "external-api",
]

LOCAL_TARGETS: List[str] = [
    "local-llm",
    "ollama-chat",
    "llama-cpp",
    "file-write",
    "file-read",
    "stdout",
    "stderr",
    "sqlite",
    "vega-db",
]


@dataclass
class GatewayResult:
    """The result of a routed gateway call.

    Attributes:
        ok: Whether the call succeeded (blocked actions are not ok).
        data: The payload returned by the tool / LLM.
        audit_id: Unique audit reference for this call.
        blocked: True if the call was blocked by scope enforcement.
        reason: Human-readable explanation (especially when blocked).
    """

    ok: bool = True
    data: Any = None
    audit_id: str = ""
    blocked: bool = False
    reason: str = ""


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _is_external(target: str) -> bool:
    """Return True if target is an external (cloud) API target."""
    return target.lower() in EXTERNAL_TARGETS


def _is_local(target: str) -> bool:
    """Return True if target is a known local target."""
    return target.lower() in LOCAL_TARGETS


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate text to max_len characters, appending '...' if needed."""
    cleaned = text.replace("\n", " ").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3] + "..."


def _extract_scope_and_summary(data: Any, target: str) -> Tuple[str, str]:
    """Extract data scope and a human-readable summary from arbitrary data.

    Args:
        data: The data being sent through the gateway.
        target: The target (used for fallback scoping).

    Returns:
        A (scope, summary) tuple.
    """
    if isinstance(data, UserData):
        return data.scope, data.content_summary()

    if hasattr(data, "scope") and hasattr(data, "content"):
        try:
            scope_val = data.scope
            content_val = getattr(data, "content", str(data))
            if isinstance(content_val, str):
                summary = _truncate(content_val, 80)
            else:
                summary = _truncate(str(content_val), 80)
            return scope_val, summary
        except Exception:
            pass

    if isinstance(data, str):
        if _is_external(target):
            scope = SCOPE_SHAREABLE
        elif _is_local(target) or "local" in target.lower() or "file" in target.lower():
            scope = SCOPE_LOCAL
        else:
            scope = SCOPE_CONTEXT_FOR_LLM
        return scope, _truncate(data, 80)

    return SCOPE_CONTEXT_FOR_LLM, _truncate(str(data), 80)


# --------------------------------------------------------------------------
# Core routing
# --------------------------------------------------------------------------


def route_tool_call(
    action: str,
    target: str,
    data: Any,
    model_used: Optional[str] = None,
    why: str = "",
) -> GatewayResult:
    """Route a tool call through the privacy gateway.

    This is the primary entry point for all tool invocations.

    Steps:
    1. Determine the scope of the incoming data.
    2. If the data is local and the target is external, block the call.
    3. Log the action to the audit trail.
    4. Return a GatewayResult with the audit reference.

    Args:
        action: Short verb (e.g. llm_invoke, file_read, tool_call).
        target: Where the action is headed (e.g. openai-chat, local-llm).
        data: The data being sent. Can be a raw string or UserData instance.
        model_used: Model identifier, if applicable.
        why: Free-text justification for this action.

    Returns:
        A GatewayResult.
    """
    scope, content_summary = _extract_scope_and_summary(data, target)
    is_remote = _is_external(target)

    # BLOCK: local data to external target
    if scope == SCOPE_LOCAL and is_remote:
        audit_id = _audit.log(
            action="blocked_" + action,
            target=target,
            model_used=model_used,
            data_summary=content_summary,
            why=f"BLOCKED: {why} (local-scoped data cannot be sent to external target)",
        )
        return GatewayResult(
            ok=False,
            data=None,
            audit_id=audit_id,
            blocked=True,
            reason=(
                f"Data with scope '{SCOPE_LOCAL}' cannot be sent to "
                f"external target '{target}'. This action was blocked."
            ),
        )

    # AUDIT: log the call
    audit_id = _audit.log(
        action=action,
        target=target,
        model_used=model_used,
        data_summary=content_summary,
        why=why,
    )

    return GatewayResult(
        ok=True,
        data=data,
        audit_id=audit_id,
        blocked=False,
        reason="",
    )


def route_llm_call(
    prompt: str,
    target: str = "openrouter-chat",
    model: Optional[str] = None,
    why: str = "Agent reasoning / response generation",
) -> GatewayResult:
    """Convenience wrapper for routing an LLM call.

    Automatically wraps route_tool_call with action='llm_invoke'.

    Args:
        prompt: The prompt being sent to the LLM.
        target: The LLM provider endpoint.
        model: Model identifier.
        why: Justification.

    Returns:
        A GatewayResult.
    """
    scope = SCOPE_SHAREABLE if _is_external(target) else SCOPE_CONTEXT_FOR_LLM
    user_data = UserData(
        scope=scope,
        content=prompt,
        source="agent-routing",
        tag="llm-prompt",
    )
    return route_tool_call(
        action="llm_invoke",
        target=target,
        data=user_data,
        model_used=model,
        why=why,
    )
