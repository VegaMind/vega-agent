"""Node data structures for the Vega Context Tree.

Defines the dataclasses used throughout the context tree subsystem:
Node, Edge, and BranchSummaryStats.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class NodeType(str, Enum):
    """Types of nodes in the context tree."""

    ROOT = "root"
    BRANCH = "branch"
    LEAF = "leaf"


class RelationshipType(str, Enum):
    """Types of relationships between nodes."""

    DEPENDS_ON = "depends_on"
    REFERENCES = "references"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"


@dataclass
class Node:
    """A node in the context tree.

    Attributes:
        node_id: Unique identifier (UUID4 hex).
        type: One of root, branch, leaf.
        parent_id: ID of the parent node, or None for root nodes.
        title: Human-readable title.
        content: Markdown/text content.
        importance: Float 0.0-1.0 indicating importance.
        created_at: UTC timestamp of creation.
        last_accessed: UTC timestamp of last access.
        access_count: Number of times this node has been accessed.
        ttl_seconds: Time-to-live in seconds (None = no expiry).
        is_archived: Whether the node has been archived.
        tags: Optional list of tags for categorization.
        source: Optional string indicating origin (e.g., 'obsidian', 'manual').
    """

    node_id: str = field(
        default_factory=lambda: uuid.uuid4().hex
    )
    type: NodeType = NodeType.LEAF
    parent_id: Optional[str] = None
    title: str = ""
    content: str = ""
    importance: float = 0.5
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_accessed: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    is_archived: bool = False
    tags: list[str] = field(default_factory=list)
    source: Optional[str] = None

    def touch(self) -> None:
        """Mark this node as accessed now. Updates last_accessed and increments
        access_count."""
        self.last_accessed = datetime.now(timezone.utc).isoformat()
        self.access_count += 1

    def importance_decayed(self, weeks: float = 1.0) -> float:
        """Return importance after decay of 5% per week.

        Args:
            weeks: Number of weeks of decay to apply (default 1.0).

        Returns:
            Decayed importance value (clamped >= 0.0).
        """
        decayed = self.importance * (0.95 ** weeks)
        return max(0.0, decayed)

    def is_expired(self) -> bool:
        """Check if the node's TTL has expired.

        Returns:
            True if ttl_seconds is set and the node is older than ttl_seconds.
        """
        if self.ttl_seconds is None:
            return False
        created = datetime.fromisoformat(self.created_at)
        now = datetime.now(timezone.utc)
        age = (now - created).total_seconds()
        return age > self.ttl_seconds


@dataclass
class Edge:
    """A directed relationship between two nodes.

    Attributes:
        edge_id: Unique identifier.
        source_id: ID of the source node.
        target_id: ID of the target node.
        relationship: Type of relationship.
        strength: Float 0.0-1.0 indicating strength of connection.
        created_at: UTC timestamp.
    """

    edge_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    source_id: str = ""
    target_id: str = ""
    relationship: RelationshipType = RelationshipType.REFERENCES
    strength: float = 0.5
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class BranchSummaryStats:
    """Aggregate statistics for a branch node.

    Attributes:
        branch_id: ID of the branch node.
        total_leaves: Number of leaf nodes under this branch.
        active_leaves: Number of non-archived leaf nodes.
        avg_importance: Average importance of active leaves.
        total_size_bytes: Total content size of all leaves.
        oldest_leaf_age_days: Age in days of the oldest leaf.
    """

    branch_id: str = ""
    total_leaves: int = 0
    active_leaves: int = 0
    avg_importance: float = 0.0
    total_size_bytes: int = 0
    oldest_leaf_age_days: float = 0.0
