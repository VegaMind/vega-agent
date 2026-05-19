"""Data boundary types for the Vega Privacy Layer.

Defines the simple dataclass types that Vega uses to classify data
scope and enforce privacy boundaries — UserData (local/context/llm/shareable
classification) and AgentOutput (what the agent produced and where it went).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────
# Scope constants  (simple strings — not an enum, keeps it YAML-friendly)
# ──────────────────────────────────────────────────────────────────────────

SCOPE_LOCAL = "local"
"""Data that must never leave this machine (passwords, keys, personal notes)."""

SCOPE_CONTEXT_FOR_LLM = "context_for_llm"
"""Data that may be sent to a local LLM but not to any external/cloud API."""

SCOPE_SHAREABLE = "shareable"
"""Data that may be sent to external APIs (but still audited)."""

ALL_SCOPES = (SCOPE_LOCAL, SCOPE_CONTEXT_FOR_LLM, SCOPE_SHAREABLE)


# ──────────────────────────────────────────────────────────────────────────
# Boundary types
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class UserData:
    """Represents a piece of data belonging to the user, classified by scope.

    The scope determines where the data is allowed to travel:

    * ``local``          — Never leaves this machine.  (e.g. API keys, secrets)
    * ``context_for_llm`` — May be sent to a *local* LLM but **not** to any
                            external / cloud API.
    * ``shareable``       — May be sent to external APIs.  Every transmission
                            is still logged in the audit trail.

    Attributes:
        scope: One of ``"local"``, ``"context_for_llm"``, ``"shareable"``.
        content: The actual data payload.
        source: Free-text label describing where this data came from
            (e.g. ``"config.yaml"``, ``"user-input"``, ``"obsidian-vault"``).
        tag: Optional human-readable tag for quick identification.
    """

    scope: str = SCOPE_SHAREABLE
    content: str = ""
    source: str = ""
    tag: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate scope on construction."""
        if self.scope not in ALL_SCOPES:
            raise ValueError(
                f"Invalid scope {self.scope!r}. Must be one of {ALL_SCOPES}."
            )

    def content_summary(self, max_chars: int = 80) -> str:
        """Return a truncated, safe summary of the content for audit logs.

        Args:
            max_chars: Maximum length of the summary (default 80).

        Returns:
            Truncated content string suitable for logging.
        """
        text = self.content.replace("\n", " ").strip()
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3] + "..."

    def content_hash(self) -> str:
        """SHA-256 hex digest of the content.

        Useful for deduplication and tamper-evident audit entries.
        """
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


@dataclass
class AgentOutput:
    """Records what the agent produced and where it was delivered.

    Every tool-call or LLM-invocation that produces output should create
    one of these so the audit trail can answer "what did the agent do
    and where did the result go?"

    Attributes:
        output_type: Kind of output (e.g. ``"text"``, ``"file"``, ``"api_call"``).
        target: Where the output was delivered (e.g. ``"stdout"``,
            ``"/path/to/file"``, ``"openai-chat"``).
        content_hash: SHA-256 hex digest of the output content.
        llm_used: Identifier of the model that produced this output
            (e.g. ``"deepseek/deepseek-v4"``).  May be ``None`` for
            deterministic / non-LLM outputs.
        timestamp: ISO-8601 UTC timestamp of when the output was created.
    """

    output_type: str = "text"
    target: str = ""
    content_hash: str = ""
    llm_used: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def from_content(
        cls,
        content: str,
        output_type: str = "text",
        target: str = "",
        llm_used: Optional[str] = None,
    ) -> AgentOutput:
        """Build an AgentOutput from raw content (auto-hashes it).

        Args:
            content: The output content to hash.
            output_type: Kind of output.
            target: Where the output was delivered.
            llm_used: Model identifier.

        Returns:
            A new ``AgentOutput`` instance.
        """
        return cls(
            output_type=output_type,
            target=target,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            llm_used=llm_used,
        )
