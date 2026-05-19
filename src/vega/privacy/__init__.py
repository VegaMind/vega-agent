"""Vega Privacy Layer — Audit + Boundary Types + Optional Encryption.

Vega's approach to privacy is **transparent audit logging** and **simple
data-boundary types**.  We do **not** attempt cryptographic provable
privacy (like OpenHuman).  Instead we focus on what matters most for a
local-first personal agent:

* **Audit log** — every tool-call, LLM-invocation, and data-access is
  recorded as human-readable JSONL.
* **Boundaries** — every piece of user data is tagged with a scope
  (``local`` / ``context_for_llm`` / ``shareable``) and the gateway
  enforces those scopes.
* **Optional encryption** — convenience helpers for encrypting local
  data at rest via Fernet.

Typical usage::

    from vega.privacy import audit, UserData, AgentOutput, log_audit

    # Tag incoming user data
    ud = UserData(scope="local", content="my secret", source="user-input")

    # Log an action
    audit_id = log_audit("tool_call", target="openai-chat", ...)
"""

from __future__ import annotations

from vega.privacy.audit import (
    count_entries,
    list_log_files,
    log as log_audit,
    read_all,
    read_recent,
)
from vega.privacy.boundary import (
    ALL_SCOPES,
    SCOPE_CONTEXT_FOR_LLM,
    SCOPE_LOCAL,
    SCOPE_SHAREABLE,
    AgentOutput,
    UserData,
)
from vega.privacy.encrypt import (
    decrypt,
    decrypt_file,
    derive_key,
    encrypt,
    encrypt_file,
    generate_key,
)

__all__ = [
    # Audit
    "log_audit",
    "read_recent",
    "read_all",
    "list_log_files",
    "count_entries",
    # Scopes
    "SCOPE_LOCAL",
    "SCOPE_CONTEXT_FOR_LLM",
    "SCOPE_SHAREABLE",
    "ALL_SCOPES",
    # Boundary types
    "UserData",
    "AgentOutput",
    # Encryption
    "generate_key",
    "derive_key",
    "encrypt",
    "decrypt",
    "encrypt_file",
    "decrypt_file",
]
