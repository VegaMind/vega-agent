"""Vega Memory Subsystem — ChromaDB vector store wrapper.

Provides persistent, local vector storage for semantic recall (memories)
and recent interaction history (episodic).

Exports:
    MemoryStore — the main ChromaDB wrapper class.
"""

from __future__ import annotations

from vega.memory.vector import MemoryStore

__all__ = [
    "MemoryStore",
]