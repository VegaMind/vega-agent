"""Auto-pruning and condensation logic for the Vega Context Tree.

Handles:
- Archiving low-importance, unused nodes.
- Importance decay simulation.
- Branch condensation (summarizing many leaves into one).
"""

from __future__ import annotations

from typing import Callable, Optional

from vega.context_tree.db import ContextTreeDB
from vega.context_tree.node import Node, NodeType

# ── Archiving ──────────────────────────────────────────────────────────


def get_archivable_nodes(
    db: ContextTreeDB,
    importance_threshold: float = 0.1,
    days_unused: float = 30.0,
) -> list[Node]:
    """Get nodes eligible for automatic archiving.

    A node is archivable when its importance is below the threshold
    and it hasn't been accessed in the specified number of days.

    Args:
        db: The context tree database instance.
        importance_threshold: Maximum importance (default 0.1).
        days_unused: Minimum days since last access (default 30.0).

    Returns:
        List of nodes to archive.
    """
    return db.get_archivable_nodes(
        importance_threshold=importance_threshold,
        days_unused=days_unused,
    )


def archive_nodes(db: ContextTreeDB, nodes: list[Node]) -> int:
    """Archive a list of nodes.

    Marks each node's ``is_archived`` flag to ``True``.

    Args:
        db: The context tree database instance.
        nodes: Nodes to archive.

    Returns:
        Number of nodes archived.
    """
    count = 0
    for node in nodes:
        node.is_archived = True
        db.archive_node(node.node_id)
        count += 1
    return count


def run_archive_pass(
    db: ContextTreeDB,
    importance_threshold: float = 0.1,
    days_unused: float = 30.0,
) -> int:
    """Perform a full archive sweep.

    Convenience function that finds archivable nodes and archives them.

    Args:
        db: The context tree database instance.
        importance_threshold: See :func:`get_archivable_nodes`.
        days_unused: See :func:`get_archivable_nodes`.

    Returns:
        Number of nodes archived.
    """
    nodes = get_archivable_nodes(db, importance_threshold, days_unused)
    return archive_nodes(db, nodes)


# ── Importance Decay ──────────────────────────────────────────────────


def apply_importance_decay(
    db: ContextTreeDB,
    decay_rate: float = 0.05,
    weeks: float = 1.0,
) -> int:
    """Apply importance decay to all non-archived nodes.

    Reduces importance by ``decay_rate`` per ``weeks``.
    The decay is computed as::

        new_importance = old_importance * (1 - decay_rate) ** weeks

    Args:
        db: The context tree database instance.
        decay_rate: Fractional decay per period (default 0.05 = 5%).
        weeks: Number of week-periods to decay (default 1.0).

    Returns:
        Number of nodes updated.
    """
    nodes = db.list_nodes(archived=False)
    count = 0
    factor = (1.0 - decay_rate) ** weeks

    for node in nodes:
        new_importance = node.importance * factor
        node.importance = max(0.0, new_importance)
        db.update_node(node)
        count += 1
    return count


def reinforce_node(
    db: ContextTreeDB,
    node_id: str,
    boost: float = 0.1,
    max_importance: float = 1.0,
) -> Optional[Node]:
    """Increase a node's importance (e.g., on access or relevance).

    Args:
        db: The context tree database instance.
        node_id: The node to reinforce.
        boost: Amount to add to importance (default 0.1).
        max_importance: Ceiling for importance (default 1.0).

    Returns:
        The updated Node if found, else None.
    """
    node = db.get_node(node_id)
    if node is None:
        return None
    node.importance = min(max_importance, node.importance + boost)
    db.update_node(node)
    return node


# ── Condensation ──────────────────────────────────────────────────────


def condense_branch(
    db: ContextTreeDB,
    branch_id: str,
    summarizer_func: Optional[Callable[[str], str]] = None,
    leaf_threshold: int = 50,
) -> bool:
    """Condense a branch's leaves into a single condensed leaf.

    When a branch has more than ``leaf_threshold`` leaves, all leaf
    contents are merged into one condensed node. If a
    ``summarizer_func`` is provided it will be used to generate a
    summary; otherwise contents are concatenated.

    The original leaves are archived, and a new "condensed" leaf is
    created under the same branch.

    Args:
        db: The context tree database instance.
        branch_id: The branch to condense.
        summarizer_func: Optional callable(content: str) -> summary str.
        leaf_threshold: Minimum leaf count to trigger (default 50).

    Returns:
        True if condensation was performed, False otherwise.
    """
    branch = db.get_node(branch_id)
    if branch is None or branch.type != NodeType.BRANCH:
        return False

    leaf_count = db.get_leaves_count_for_branch(branch_id)
    if leaf_count < leaf_threshold:
        return False

    leaves = db.find_children(branch_id)
    leaves = [leaf for leaf in leaves if leaf.type == NodeType.LEAF]

    # Merge all leaf content
    all_text: list[str] = []
    for leaf in leaves:
        leaf.is_archived = True
        db.archive_node(leaf.node_id)
        all_text.append(f"# {leaf.title}\n\n{leaf.content}")

    merged_content = "\n\n---\n\n".join(all_text)
    total_size = len(merged_content)

    # Summarize if we have a summarizer and content isn't tiny
    if summarizer_func is not None and total_size > 500:
        try:
            merged_content = summarizer_func(merged_content)
        except Exception:
            # Fall back to raw merge if summarization fails
            pass

    # Create condensed leaf
    condensed = Node(
        title=f"Condensed: {branch.title}",
        content=merged_content,
        type=NodeType.LEAF,
        parent_id=branch_id,
        importance=branch.importance,
        tags=branch.tags.copy() if branch.tags else [],
        source="condensed",
    )
    condensed.touch()
    db.create_node(condensed)

    return True


def find_condensable_branches(
    db: ContextTreeDB,
    leaf_threshold: int = 50,
    limit: int = 10,
) -> list[Node]:
    """Find branches that have enough leaves to justify condensation.

    Args:
        db: The context tree database instance.
        leaf_threshold: Minimum leaf count (default 50).
        limit: Maximum branches to return.

    Returns:
        List of branch Node objects eligible for condensation.
    """
    return db.get_condensable_branches(leaf_threshold=leaf_threshold)[:limit]


def run_condensation_pass(
    db: ContextTreeDB,
    summarizer_func: Optional[Callable[[str], str]] = None,
    leaf_threshold: int = 50,
    max_branches: int = 5,
) -> int:
    """Run condensation on all eligible branches.

    Args:
        db: The context tree database instance.
        summarizer_func: Optional callable(content: str) -> summary str.
        leaf_threshold: Minimum leaf count (default 50).
        max_branches: Max branches to condense in one pass (default 5).

    Returns:
        Number of branches successfully condensed.
    """
    count = 0
    for branch in find_condensable_branches(db, leaf_threshold):
        if count >= max_branches:
            break
        if condense_branch(db, branch.node_id, summarizer_func, leaf_threshold):
            count += 1
    return count


# ── Full Maintenance ──────────────────────────────────────────────────


def run_full_maintenance(
    db: ContextTreeDB,
    archive_threshold: float = 0.1,
    archive_days: float = 30.0,
    decay_rate: float = 0.05,
    decay_weeks: float = 1.0,
    condenser_func: Optional[Callable[[str], str]] = None,
    leaf_threshold: int = 50,
) -> dict[str, int]:
    """Run a full maintenance cycle: decay, archive, condense.

    Returns a report dict with counts of each action taken.

    Args:
        db: The context tree database instance.
        archive_threshold: Importance threshold for archiving.
        archive_days: Days unused threshold for archiving.
        decay_rate: Importance decay rate per week.
        decay_weeks: Number of weeks of decay to apply.
        condenser_func: Optional summarizer for condensation.
        leaf_threshold: Leaf count threshold for condensation.

    Returns:
        Dict with keys: 'decayed', 'archived', 'condensed'.
    """
    report: dict[str, int] = {"decayed": 0, "archived": 0, "condensed": 0}

    # 1. Decay importance
    decayed = apply_importance_decay(db, decay_rate, decay_weeks)
    report["decayed"] = decayed

    # 2. Archive low-importance, unused nodes
    archived = run_archive_pass(db, archive_threshold, archive_days)
    report["archived"] = archived

    # 3. Condense overgrown branches
    condensed = run_condensation_pass(db, condenser_func, leaf_threshold)
    report["condensed"] = condensed

    return report
