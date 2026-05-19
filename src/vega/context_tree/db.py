"""SQLite database layer for the Vega Context Tree.

Provides schema management, CRUD operations for nodes and edges,
and query helpers. Uses raw SQL via sqlite3 (stdlib).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from vega.context_tree.node import (
    Edge,
    Node,
    NodeType,
    RelationshipType,
)


def _get_default_db_path() -> str:
    """Return the default path for the context tree database.

    Uses ~/.vega/context_tree.db unless the VEGA_CONTEXT_DB
    environment variable is set.
    """
    env_path = os.environ.get("VEGA_CONTEXT_DB")
    if env_path:
        return env_path
    vega_dir = Path.home() / ".vega"
    vega_dir.mkdir(parents=True, exist_ok=True)
    return str(vega_dir / "context_tree.db")


class ContextTreeDB:
    """Manages the SQLite database for the context tree.

    Handles schema creation, connection management, and all
    CRUD operations for nodes and edges.

    Args:
        db_path: Path to the SQLite database file. Defaults to
            ~/.vega/context_tree.db or $VEGA_CONTEXT_DB.
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or _get_default_db_path()
        self._conn: Optional[sqlite3.Connection] = None

    # ── Connection management ──────────────────────────────────────────

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create a persistent database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        """Close the database connection if open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── Schema ─────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """Create tables and indexes if they do not exist."""
        conn = self.conn
        conn.executescript(f"""
            PRAGMA user_version = {self.SCHEMA_VERSION};

            CREATE TABLE IF NOT EXISTS nodes (
                node_id         TEXT PRIMARY KEY,
                type            TEXT NOT NULL CHECK(type IN ('root','branch','leaf')),
                parent_id       TEXT REFERENCES nodes(node_id) ON DELETE SET NULL,
                title           TEXT NOT NULL DEFAULT '',
                content         TEXT NOT NULL DEFAULT '',
                importance      REAL NOT NULL DEFAULT 0.5 CHECK(importance >= 0.0 AND importance <= 1.0),
                created_at      TEXT NOT NULL,
                last_accessed   TEXT NOT NULL,
                access_count    INTEGER NOT NULL DEFAULT 0,
                ttl_seconds     INTEGER,
                is_archived     INTEGER NOT NULL DEFAULT 0,
                tags            TEXT NOT NULL DEFAULT '[]',
                source          TEXT
            );

            CREATE TABLE IF NOT EXISTS edges (
                edge_id         TEXT PRIMARY KEY,
                source_id       TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
                target_id       TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
                relationship    TEXT NOT NULL CHECK(relationship IN ('depends_on','references','contradicts','extends')),
                strength        REAL NOT NULL DEFAULT 0.5 CHECK(strength >= 0.0 AND strength <= 1.0),
                created_at      TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_id);
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
            CREATE INDEX IF NOT EXISTS idx_nodes_importance ON nodes(importance);
            CREATE INDEX IF NOT EXISTS idx_nodes_archived ON nodes(is_archived);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(relationship);
        """)
        conn.commit()

    # ── Node CRUD ──────────────────────────────────────────────────────

    def create_node(self, node: Node) -> str:
        """Insert a new node into the database.

        Args:
            node: The Node to insert. If node.node_id is set it will be used;
                otherwise a new UUID is generated.

        Returns:
            The node_id of the created node.
        """
        conn = self.conn
        tags_json = str(node.tags)
        conn.execute(
            """
            INSERT INTO nodes
                (node_id, type, parent_id, title, content, importance,
                 created_at, last_accessed, access_count, ttl_seconds,
                 is_archived, tags, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node.node_id,
                node.type.value,
                node.parent_id,
                node.title,
                node.content,
                node.importance,
                node.created_at,
                node.last_accessed,
                node.access_count,
                node.ttl_seconds,
                1 if node.is_archived else 0,
                tags_json,
                node.source,
            ),
        )
        conn.commit()
        return node.node_id

    def get_node(self, node_id: str) -> Optional[Node]:
        """Retrieve a single node by ID.

        Args:
            node_id: The node's unique identifier.

        Returns:
            A Node instance if found, else None.
        """
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        return self._row_to_node(row) if row else None

    def update_node(self, node: Node) -> None:
        """Update an existing node in the database.

        All fields are overwritten from the provided Node object.

        Args:
            node: The Node with updated values. Its node_id must exist.
        """
        tags_json = str(node.tags)
        self.conn.execute(
            """
            UPDATE nodes SET
                type = ?, parent_id = ?, title = ?, content = ?,
                importance = ?, created_at = ?, last_accessed = ?,
                access_count = ?, ttl_seconds = ?, is_archived = ?,
                tags = ?, source = ?
            WHERE node_id = ?
            """,
            (
                node.type.value,
                node.parent_id,
                node.title,
                node.content,
                node.importance,
                node.created_at,
                node.last_accessed,
                node.access_count,
                node.ttl_seconds,
                1 if node.is_archived else 0,
                tags_json,
                node.source,
                node.node_id,
            ),
        )
        self.conn.commit()

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and all edges referencing it.

        Args:
            node_id: The node to delete.

        Returns:
            True if a row was deleted, False if not found.
        """
        cursor = self.conn.execute(
            "DELETE FROM nodes WHERE node_id = ?", (node_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def list_nodes(
        self,
        type_filter: Optional[NodeType] = None,
        parent_id: Optional[str] = None,
        archived: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Node]:
        """List nodes with optional filters.

        Args:
            type_filter: If set, only return nodes of this type.
            parent_id: If set, only return children of this parent.
            archived: If True/False, filter by archived status.
            limit: Maximum number of results (default 100).
            offset: Pagination offset.

        Returns:
            A list of matching Node objects.
        """
        conditions: list[str] = []
        params: list = []

        if type_filter is not None:
            conditions.append("type = ?")
            params.append(type_filter.value)
        if parent_id is not None:
            conditions.append("parent_id = ?")
            params.append(parent_id)
        if archived is not None:
            conditions.append("is_archived = ?")
            params.append(1 if archived else 0)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        rows = self.conn.execute(
            f"SELECT * FROM nodes {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def find_children(self, parent_id: str) -> list[Node]:
        """Find all direct children of a given node.

        Args:
            parent_id: The parent node ID.

        Returns:
            List of child Node objects.
        """
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE parent_id = ?", (parent_id,)
        ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def search_nodes(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Node]:
        """Search nodes by title and content (LIKE-based).

        Args:
            query: Search term.
            limit: Maximum results.

        Returns:
            List of matching Node objects.
        """
        pattern = f"%{query}%"
        rows = self.conn.execute(
            """
            SELECT * FROM nodes
            WHERE title LIKE ? OR content LIKE ?
            ORDER BY importance DESC, last_accessed DESC
            LIMIT ?
            """,
            (pattern, pattern, limit),
        ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def get_root_nodes(self) -> list[Node]:
        """Get all nodes of type 'root' (identity/persona nodes).

        Returns:
            List of root Node objects.
        """
        return self.list_nodes(type_filter=NodeType.ROOT)

    def touch_node(self, node_id: str) -> None:
        """Update last_accessed timestamp and increment access_count.

        Args:
            node_id: The node to touch.
        """
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            UPDATE nodes
            SET last_accessed = ?, access_count = access_count + 1
            WHERE node_id = ?
            """,
            (now, node_id),
        )
        self.conn.commit()

    # ── Edge CRUD ──────────────────────────────────────────────────────

    def create_edge(self, edge: Edge) -> str:
        """Insert a new edge into the database.

        Args:
            edge: The Edge to insert.

        Returns:
            The edge_id of the created edge.
        """
        self.conn.execute(
            """
            INSERT INTO edges
                (edge_id, source_id, target_id, relationship, strength, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                edge.edge_id,
                edge.source_id,
                edge.target_id,
                edge.relationship.value,
                edge.strength,
                edge.created_at,
            ),
        )
        self.conn.commit()
        return edge.edge_id

    def get_edges_for_node(
        self,
        node_id: str,
        direction: str = "outgoing",
    ) -> list[Edge]:
        """Get all edges connected to a node.

        Args:
            node_id: The node ID.
            direction: 'outgoing' (source_id matches), 'incoming'
                (target_id matches), or 'both'.

        Returns:
            List of Edge objects.
        """
        if direction == "outgoing":
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE source_id = ?", (node_id,)
            ).fetchall()
        elif direction == "incoming":
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE target_id = ?", (node_id,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE source_id = ? OR target_id = ?",
                (node_id, node_id),
            ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge by ID.

        Args:
            edge_id: The edge to delete.

        Returns:
            True if deleted, False if not found.
        """
        cursor = self.conn.execute(
            "DELETE FROM edges WHERE edge_id = ?", (edge_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    # ── Statistics / Queries ───────────────────────────────────────────

    def count_nodes(self) -> int:
        """Return total number of nodes in the database."""
        row = self.conn.execute("SELECT COUNT(*) AS cnt FROM nodes").fetchone()
        return row["cnt"] if row else 0

    def count_edges(self) -> int:
        """Return total number of edges in the database."""
        row = self.conn.execute("SELECT COUNT(*) AS cnt FROM edges").fetchone()
        return row["cnt"] if row else 0

    def get_branch_summary(self, branch_id: str) -> dict:
        """Get summary statistics for a branch node and its leaves.

        Args:
            branch_id: The branch node ID.

        Returns:
            Dict with keys: total_leaves, active_leaves, avg_importance,
            total_size_bytes, oldest_leaf_age_days.
        """
        now = datetime.now(timezone.utc).isoformat()
        row = self.conn.execute(
            """
            SELECT
                COUNT(*)                                              AS total_leaves,
                SUM(CASE WHEN is_archived = 0 THEN 1 ELSE 0 END)     AS active_leaves,
                COALESCE(AVG(CASE WHEN is_archived = 0 THEN importance END), 0.0)
                                                                      AS avg_importance,
                COALESCE(SUM(LENGTH(content)), 0)                     AS total_size_bytes,
                COALESCE(MIN(julianday(?) - julianday(created_at)), 0)
                                                                      AS oldest_leaf_age_days
            FROM nodes
            WHERE parent_id = ? AND type = 'leaf'
            """,
            (now, branch_id),
        ).fetchone()
        return dict(row) if row else {}

    def get_leaves_count_for_branch(self, branch_id: str) -> int:
        """Count leaves directly under a given branch.

        Args:
            branch_id: The branch node ID.

        Returns:
            Leaf count.
        """
        row = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM nodes WHERE parent_id = ? AND type = 'leaf'",
            (branch_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_archivable_nodes(
        self,
        importance_threshold: float = 0.1,
        days_unused: float = 30.0,
    ) -> list[Node]:
        """Find nodes eligible for archiving.

        Nodes are considered archivable when:
        - importance < threshold
        - last_accessed is older than days_unused
        - not already archived

        Args:
            importance_threshold: Importance cutoff (default 0.1).
            days_unused: Days since last access (default 30.0).

        Returns:
            List of Node objects eligible for archiving.
        """
        rows = self.conn.execute(
            """
            SELECT * FROM nodes
            WHERE importance < ?
              AND is_archived = 0
              AND julianday('now') - julianday(last_accessed) > ?
            ORDER BY last_accessed ASC
            """,
            (importance_threshold, days_unused),
        ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def archive_node(self, node_id: str) -> None:
        """Mark a node as archived.

        Args:
            node_id: The node to archive.
        """
        self.conn.execute(
            "UPDATE nodes SET is_archived = 1 WHERE node_id = ?", (node_id,)
        )
        self.conn.commit()

    def get_condensable_branches(self, leaf_threshold: int = 50) -> list[Node]:
        """Find branches that have many leaves and may need condensation.

        Args:
            leaf_threshold: Minimum number of leaves to consider (default 50).

        Returns:
            List of branch Node objects exceeding the threshold.
        """
        rows = self.conn.execute(
            """
            SELECT n.*, COUNT(c.node_id) AS leaf_count
            FROM nodes n
            INNER JOIN nodes c ON c.parent_id = n.node_id AND c.type = 'leaf'
            WHERE n.type = 'branch'
            GROUP BY n.node_id
            HAVING leaf_count >= ?
            """,
            (leaf_threshold,),
        ).fetchall()
        return [self._row_to_node(r) for r in rows]

    # ── Migration helpers ──────────────────────────────────────────────

    def bulk_insert_nodes(self, nodes: list[Node]) -> list[str]:
        """Insert multiple nodes in a single transaction.

        Args:
            nodes: List of Node objects to insert.

        Returns:
            List of node_ids inserted.
        """
        conn = self.conn
        ids: list[str] = []
        for node in nodes:
            tags_json = str(node.tags)
            conn.execute(
                """
                INSERT OR IGNORE INTO nodes
                    (node_id, type, parent_id, title, content, importance,
                     created_at, last_accessed, access_count, ttl_seconds,
                     is_archived, tags, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.node_id,
                    node.type.value,
                    node.parent_id,
                    node.title,
                    node.content,
                    node.importance,
                    node.created_at,
                    node.last_accessed,
                    node.access_count,
                    node.ttl_seconds,
                    1 if node.is_archived else 0,
                    tags_json,
                    node.source,
                ),
            )
            ids.append(node.node_id)
        conn.commit()
        return ids

    # ── Internal helpers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> Node:
        """Convert a SQLite row to a Node dataclass."""
        import json

        tags_raw = row["tags"] if row["tags"] else "[]"
        try:
            tags = json.loads(tags_raw)
        except (json.JSONDecodeError, TypeError):
            tags = []

        return Node(
            node_id=row["node_id"],
            type=NodeType(row["type"]),
            parent_id=row["parent_id"],
            title=row["title"],
            content=row["content"],
            importance=float(row["importance"]),
            created_at=row["created_at"],
            last_accessed=row["last_accessed"],
            access_count=int(row["access_count"]),
            ttl_seconds=row["ttl_seconds"],
            is_archived=bool(row["is_archived"]),
            tags=tags,
            source=row["source"],
        )

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> Edge:
        """Convert a SQLite row to an Edge dataclass."""
        return Edge(
            edge_id=row["edge_id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            relationship=RelationshipType(row["relationship"]),
            strength=float(row["strength"]),
            created_at=row["created_at"],
        )
