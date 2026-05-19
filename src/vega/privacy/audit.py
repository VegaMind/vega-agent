"""Audit log manager for Vega.

Writes and reads a JSONL audit trail at ``~/.vega/audit/YYYY-MM-DD.jsonl``.
Every tool call, LLM invocation, or data-access is recorded here — human-readable,
machine-parseable, and never automatically deleted.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


def _ensure_audit_dir() -> Path:
    """Return the path to the audit directory, creating it if necessary.

    The directory is ``~/.vega/audit/``.

    Returns:
        Path to the audit directory.
    """
    audit_dir = Path.home() / ".vega" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir


def _todays_log_path() -> Path:
    """Return the filesystem path for today's JSONL audit file.

    Returns:
        Path like ``~/.vega/audit/2026-05-19.jsonl``.
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _ensure_audit_dir() / f"{date_str}.jsonl"


# ──────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────


def log(
    action: str,
    target: str = "",
    model_used: Optional[str] = None,
    data_summary: str = "",
    why: str = "",
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Write a single entry to the audit log.

    Args:
        action: Short verb describing what happened (``"tool_call"``,
            ``"llm_invoke"``, ``"file_read"``, ``"blocked_action"``, ...).
        target: What the action operated on (e.g. a tool name, ``"openai-chat"``,
            ``"/home/user/secret.txt"``).
        model_used: Which model was invoked, if any.
        data_summary: Human-readable summary of the data involved.
        why: Free-text justification for why this action happened.
        extra: Optional dict of additional structured data to include.

    Returns:
        The generated ``audit_id`` (a short hex string) so callers can
        reference this entry later.
    """
    entry = _build_entry(action, target, model_used, data_summary, why, extra)
    path = _todays_log_path()

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    return entry["audit_id"]


def read_recent(lines: int = 20, path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read the most recent *lines* entries from the audit log.

    Args:
        lines: How many entries to return (default 20).
        path: Specific log file to read.  Defaults to today's file.

    Returns:
        List of audit-entry dicts, most recent first.
    """
    file = path or _todays_log_path()
    if not file.exists():
        return []

    all_entries: List[Dict[str, Any]] = []
    with open(file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_entries.append(json.loads(line))

    # Most-recent-first
    return list(reversed(all_entries))[:lines]


def read_all(path: Optional[Path] = None) -> Iterator[Dict[str, Any]]:
    """Yield audit entries from a log file (oldest first).

    This is a generator so it won't load huge files into memory.

    Args:
        path: Specific log file.  Defaults to today's file.
    """
    file = path or _todays_log_path()
    if not file.exists():
        return

    with open(file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def list_log_files() -> List[Path]:
    """Return paths to every JSONL audit file found under ``~/.vega/audit/``.

    Files are sorted oldest-first.

    Returns:
        List of Path objects.
    """
    audit_dir = _ensure_audit_dir()
    files = sorted(audit_dir.glob("*.jsonl"))
    return files


def count_entries(path: Optional[Path] = None) -> int:
    """Count the number of audit entries in a log file.

    Args:
        path: Specific log file.  Defaults to today's file.

    Returns:
        Entry count.
    """
    file = path or _todays_log_path()
    if not file.exists():
        return 0

    count = 0
    with open(file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1

    return count


# ──────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────


def _build_entry(
    action: str,
    target: str,
    model_used: Optional[str],
    data_summary: str,
    why: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble a single audit-log entry dict."""
    return {
        "audit_id": uuid.uuid4().hex[:12],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "target": target,
        "model_used": model_used,
        "data_summary": data_summary,
        "why": why,
        **(extra or {}),
    }
