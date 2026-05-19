"""Vega Context Tree — Core Knowledge Management System.

The Context Tree is the central knowledge store for the Vega Agent.
It replaces Obsidian vaults with a structured, ephemeral-aware,
and self-maintaining knowledge graph backed by SQLite.

Submodules:
    node        — Node, Edge, and BranchSummaryStats dataclasses.
    db          — SQLite database layer with schema and CRUD operations.
    pruning     — Auto-pruning, importance decay, and condensation.
    migration   — Obsidian vault import utilities.
"""

from vega.context_tree.db import ContextTreeDB
from vega.context_tree.migration import MigrationReport, migrate_from_obsidian
from vega.context_tree.node import (
    BranchSummaryStats,
    Edge,
    Node,
    NodeType,
    RelationshipType,
)
from vega.context_tree.pruning import (
    archive_nodes,
    condense_branch,
    find_condensable_branches,
    get_archivable_nodes,
    reinforce_node,
    run_archive_pass,
    run_condensation_pass,
    run_full_maintenance,
)

__all__ = [
    # Node types
    "Node",
    "Edge",
    "NodeType",
    "RelationshipType",
    "BranchSummaryStats",
    # Database
    "ContextTreeDB",
    # Migration
    "migrate_from_obsidian",
    "MigrationReport",
    # Pruning
    "get_archivable_nodes",
    "archive_nodes",
    "run_archive_pass",
    "reinforce_node",
    "find_condensable_branches",
    "condense_branch",
    "run_condensation_pass",
    "run_full_maintenance",
]
