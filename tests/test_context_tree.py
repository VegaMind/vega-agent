"""Comprehensive tests for the Vega Context Tree subsystem."""

from __future__ import annotations

import os
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytest

from vega.context_tree.node import (
    Node,
    NodeType,
    Edge,
    RelationshipType,
    BranchSummaryStats,
)
from vega.context_tree.db import ContextTreeDB
from vega.context_tree.pruning import (
    get_archivable_nodes,
    archive_nodes,
    run_archive_pass,
    reinforce_node,
    condense_branch,
    find_condensable_branches,
    run_condensation_pass,
    run_full_maintenance,
    apply_importance_decay,
)
from vega.context_tree.migration import (
    migrate_from_obsidian,
    MigrationReport,
    parse_obsidian_frontmatter,
    extract_obsidian_links,
    extract_tags_from_content,
    scan_vault,
)


# ═════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture
def db():
    """Create a fresh ContextTreeDB backed by a temp file for each test."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    database = ContextTreeDB(db_path=tmp.name)
    database.initialize()
    yield database
    database.close()
    os.unlink(tmp.name)


@pytest.fixture
def sample_root(db):
    """Insert a root node and return it."""
    root = Node(type=NodeType.ROOT, title="Vega Ident", importance=1.0)
    db.create_node(root)
    return root


@pytest.fixture
def sample_branch(db, sample_root):
    """Insert a branch under root and return it."""
    branch = Node(
        type=NodeType.BRANCH,
        parent_id=sample_root.node_id,
        title="Projects",
        importance=0.8,
    )
    db.create_node(branch)
    return branch


@pytest.fixture
def sample_leaf(db, sample_branch):
    """Insert a leaf under branch and return it."""
    leaf = Node(
        type=NodeType.LEAF,
        parent_id=sample_branch.node_id,
        title="My Idea",
        content="This is a great idea.",
        importance=0.6,
    )
    db.create_node(leaf)
    return leaf


# ═════════════════════════════════════════════════════════════════════════
# Node tests
# ═════════════════════════════════════════════════════════════════════════


class TestNodeDataclass:
    def test_default_node(self):
        node = Node()
        assert node.node_id is not None and len(node.node_id) == 32
        assert node.type == NodeType.LEAF
        assert node.importance == 0.5
        assert node.is_archived is False
        assert node.access_count == 0
        assert isinstance(node.tags, list)

    def test_touch_updates_access(self):
        node = Node()
        old_accessed = node.last_accessed
        node.touch()
        assert node.access_count == 1
        assert node.last_accessed >= old_accessed

    def test_importance_decay(self):
        node = Node(importance=1.0)
        decayed = node.importance_decayed(weeks=1.0)
        assert decayed == pytest.approx(0.95, rel=1e-3)

    def test_importance_decay_multi_week(self):
        node = Node(importance=1.0)
        decayed = node.importance_decayed(weeks=4.0)
        assert decayed == pytest.approx(0.95**4, rel=1e-3)

    def test_expired_ttl(self):
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        node = Node(
            created_at=old.isoformat(),
            ttl_seconds=3600,  # 1 hour
        )
        assert node.is_expired() is True

    def test_not_expired(self):
        node = Node(ttl_seconds=3600)
        assert node.is_expired() is False

    def test_no_ttl(self):
        node = Node()
        assert node.is_expired() is False

    def test_node_type_enum_values(self):
        assert NodeType.ROOT.value == "root"
        assert NodeType.BRANCH.value == "branch"
        assert NodeType.LEAF.value == "leaf"

    def test_relationship_enum_values(self):
        assert RelationshipType.DEPENDS_ON.value == "depends_on"
        assert RelationshipType.REFERENCES.value == "references"
        assert RelationshipType.CONTRADICTS.value == "contradicts"
        assert RelationshipType.EXTENDS.value == "extends"


# ═════════════════════════════════════════════════════════════════════════
# Edge tests
# ═════════════════════════════════════════════════════════════════════════


class TestEdgeDataclass:
    def test_default_edge(self):
        edge = Edge()
        assert edge.relationship == RelationshipType.REFERENCES
        assert edge.strength == 0.5


class TestBranchSummaryStats:
    def test_defaults(self):
        stats = BranchSummaryStats()
        assert stats.total_leaves == 0
        assert stats.active_leaves == 0


# ═════════════════════════════════════════════════════════════════════════
# Database tests
# ═════════════════════════════════════════════════════════════════════════


class TestContextTreeDB:
    def test_initialize_creates_tables(self, db):
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r["name"] for r in tables]
        assert "nodes" in names
        assert "edges" in names

    def test_create_and_get_node(self, db):
        node = Node(title="Test", importance=0.7)
        node_id = db.create_node(node)
        fetched = db.get_node(node_id)
        assert fetched is not None
        assert fetched.node_id == node_id
        assert fetched.title == "Test"
        assert fetched.importance == 0.7

    def test_create_and_get_node_no_id(self, db):
        node = Node(title="No ID")
        node_id = db.create_node(node)
        assert node_id is not None
        fetched = db.get_node(node_id)
        assert fetched is not None
        assert fetched.title == "No ID"

    def test_get_node_not_found(self, db):
        assert db.get_node("nonexistent") is None

    def test_update_node(self, db, sample_leaf):
        sample_leaf.title = "Updated Title"
        sample_leaf.importance = 0.9
        db.update_node(sample_leaf)
        fetched = db.get_node(sample_leaf.node_id)
        assert fetched.title == "Updated Title"
        assert fetched.importance == 0.9

    def test_delete_node(self, db, sample_leaf):
        assert db.delete_node(sample_leaf.node_id) is True
        assert db.get_node(sample_leaf.node_id) is None

    def test_delete_nonexistent(self, db):
        assert db.delete_node("nope") is False

    def test_list_nodes_type_filter(self, db, sample_root, sample_branch, sample_leaf):
        roots = db.list_nodes(type_filter=NodeType.ROOT)
        assert len(roots) == 1
        branches = db.list_nodes(type_filter=NodeType.BRANCH)
        assert len(branches) == 1
        leaves = db.list_nodes(type_filter=NodeType.LEAF)
        assert len(leaves) == 1

    def test_list_nodes_parent_filter(self, db, sample_branch, sample_leaf):
        children = db.list_nodes(parent_id=sample_branch.node_id)
        assert len(children) == 1
        assert children[0].node_id == sample_leaf.node_id

    def test_list_nodes_archived_filter(self, db, sample_leaf):
        unarchived = db.list_nodes(archived=False)
        assert len(unarchived) >= 1
        archived = db.list_nodes(archived=True)
        assert len(archived) == 0

    def test_find_children(self, db, sample_branch, sample_leaf):
        children = db.find_children(sample_branch.node_id)
        assert len(children) == 1
        assert children[0].node_id == sample_leaf.node_id

    def test_search_nodes(self, db, sample_leaf):
        results = db.search_nodes("great idea")
        assert len(results) >= 1

    def test_get_root_nodes(self, db, sample_root):
        roots = db.get_root_nodes()
        assert len(roots) >= 1

    def test_touch_node(self, db, sample_leaf):
        old_accessed = sample_leaf.last_accessed
        old_count = sample_leaf.access_count
        db.touch_node(sample_leaf.node_id)
        fetched = db.get_node(sample_leaf.node_id)
        assert fetched.access_count == old_count + 1
        assert fetched.last_accessed >= old_accessed

    def test_create_and_get_edges(self, db, sample_leaf, sample_branch):
        edge = Edge(
            source_id=sample_leaf.node_id,
            target_id=sample_branch.node_id,
            relationship=RelationshipType.REFERENCES,
        )
        edge_id = db.create_edge(edge)
        assert edge_id is not None
        edges_out = db.get_edges_for_node(sample_leaf.node_id, direction="outgoing")
        assert len(edges_out) == 1
        edges_in = db.get_edges_for_node(sample_branch.node_id, direction="incoming")
        assert len(edges_in) == 1

    def test_get_edges_both(self, db, sample_leaf, sample_branch):
        edge = Edge(
            source_id=sample_leaf.node_id,
            target_id=sample_branch.node_id,
        )
        db.create_edge(edge)
        edges = db.get_edges_for_node(sample_leaf.node_id, direction="both")
        assert len(edges) == 1

    def test_delete_edge(self, db, sample_leaf, sample_branch):
        edge = Edge(
            source_id=sample_leaf.node_id,
            target_id=sample_branch.node_id,
        )
        edge_id = db.create_edge(edge)
        assert db.delete_edge(edge_id) is True

    def test_count_nodes(self, db, sample_root, sample_branch, sample_leaf):
        assert db.count_nodes() == 3

    def test_count_edges(self, db):
        assert db.count_edges() == 0

    def test_get_branch_summary(self, db, sample_branch, sample_leaf):
        summary = db.get_branch_summary(sample_branch.node_id)
        assert summary["total_leaves"] >= 1
        assert summary["active_leaves"] >= 1

    def test_get_leaves_count_for_branch(self, db, sample_branch, sample_leaf):
        assert db.get_leaves_count_for_branch(sample_branch.node_id) == 1

    def test_get_archivable_nodes(self, db, sample_leaf):
        # sample_leaf was just created, so shouldn't be archivable
        archivable = db.get_archivable_nodes(
            importance_threshold=0.5, days_unused=0
        )
        # importance 0.6 > 0.5 so not archivable
        assert len(archivable) == 0

        # Now lower importance
        sample_leaf.importance = 0.05
        db.update_node(sample_leaf)
        archivable = db.get_archivable_nodes(
            importance_threshold=0.1, days_unused=0
        )
        assert len(archivable) >= 1

    def test_archive_node(self, db, sample_leaf):
        db.archive_node(sample_leaf.node_id)
        fetched = db.get_node(sample_leaf.node_id)
        assert fetched.is_archived is True

    def test_get_condensable_branches(self, db, sample_branch):
        # Create many leaves
        for i in range(55):
            leaf = Node(
                type=NodeType.LEAF,
                parent_id=sample_branch.node_id,
                title=f"leaf {i}",
                content=f"content {i}",
            )
            db.create_node(leaf)
        condensable = db.get_condensable_branches(leaf_threshold=50)
        assert len(condensable) == 1

    def test_bulk_insert_nodes(self, db, sample_branch):
        nodes = [
            Node(
                type=NodeType.LEAF,
                parent_id=sample_branch.node_id,
                title=f"Bulk {i}",
            )
            for i in range(10)
        ]
        ids = db.bulk_insert_nodes(nodes)
        assert len(ids) == 10

    def test_get_condensable_branches_empty(self, db):
        assert db.get_condensable_branches() == []

    def test_close(self, db):
        db.close()
        assert db._conn is None


# ═════════════════════════════════════════════════════════════════════════
# Pruning tests
# ═════════════════════════════════════════════════════════════════════════


class TestPruning:
    def test_get_archivable_nodes(self, db):
        node = Node(importance=0.05, type=NodeType.LEAF)
        # Make it look old
        old_time = (
            datetime.now(timezone.utc) - timedelta(days=60)
        ).isoformat()
        node.last_accessed = old_time
        db.create_node(node)
        archivable = get_archivable_nodes(db, importance_threshold=0.1, days_unused=30)
        assert len(archivable) >= 1

    def test_archive_nodes(self, db):
        node = Node(importance=0.05)
        db.create_node(node)
        archived = archive_nodes(db, [node])
        assert archived == 1
        fetched = db.get_node(node.node_id)
        assert fetched.is_archived is True

    def test_run_archive_pass(self, db):
        node = Node(importance=0.05)
        old_time = (
            datetime.now(timezone.utc) - timedelta(days=60)
        ).isoformat()
        node.last_accessed = old_time
        db.create_node(node)
        count = run_archive_pass(db, importance_threshold=0.1, days_unused=30)
        assert count >= 1

    def test_reinforce_node(self, db, sample_leaf):
        reinforced = reinforce_node(db, sample_leaf.node_id, boost=0.2)
        assert reinforced is not None
        assert reinforced.importance == pytest.approx(0.8, rel=1e-3)

    def test_reinforce_node_not_found(self, db):
        result = reinforce_node(db, "nonexistent", boost=0.2)
        assert result is None

    def test_reinforce_node_caps_at_max(self, db):
        node = Node(importance=0.95)
        db.create_node(node)
        reinforced = reinforce_node(db, node.node_id, boost=0.2, max_importance=1.0)
        assert reinforced.importance == 1.0

    def test_apply_importance_decay(self, db, sample_leaf):
        count = apply_importance_decay(db, decay_rate=0.05, weeks=1.0)
        assert count >= 1
        fetched = db.get_node(sample_leaf.node_id)
        assert fetched.importance == pytest.approx(0.6 * 0.95, rel=1e-3)

    def test_condense_branch_non_branch(self, db):
        result = condense_branch(db, "nonexistent")
        assert result is False

    def test_condense_branch_under_threshold(self, db, sample_branch):
        result = condense_branch(db, sample_branch.node_id, leaf_threshold=50)
        assert result is False

    def test_condense_branch(self, db, sample_branch):
        # Add enough leaves
        for i in range(55):
            leaf = Node(
                type=NodeType.LEAF,
                parent_id=sample_branch.node_id,
                title=f"leaf {i}",
                content=f"content {i}",
                source="test",
            )
            db.create_node(leaf)
        result = condense_branch(db, sample_branch.node_id, leaf_threshold=50)
        assert result is True
        # Should have created a condensed leaf
        children = db.find_children(sample_branch.node_id)
        condensed = [c for c in children if c.source == "condensed"]
        assert len(condensed) == 1
        assert "Condensed: Projects" in condensed[0].title

    def test_condense_branch_with_summarizer(self, db, sample_branch):
        for i in range(55):
            leaf = Node(
                type=NodeType.LEAF,
                parent_id=sample_branch.node_id,
                title=f"leaf {i}",
                content=f"content {i}",
            )
            db.create_node(leaf)

        def fake_summarizer(text: str) -> str:
            return "This is a summary."

        result = condense_branch(
            db, sample_branch.node_id, summarizer_func=fake_summarizer, leaf_threshold=50
        )
        assert result is True
        children = db.find_children(sample_branch.node_id)
        condensed = [c for c in children if c.source == "condensed"]
        assert len(condensed) == 1
        assert condensed[0].content == "This is a summary."

    def test_find_condensable_branches(self, db, sample_branch):
        for i in range(55):
            leaf = Node(
                type=NodeType.LEAF,
                parent_id=sample_branch.node_id,
                title=f"leaf {i}",
            )
            db.create_node(leaf)
        branches = find_condensable_branches(db, leaf_threshold=50)
        assert len(branches) == 1

    def test_run_condensation_pass(self, db, sample_branch):
        for i in range(55):
            leaf = Node(
                type=NodeType.LEAF,
                parent_id=sample_branch.node_id,
                title=f"leaf {i}",
            )
            db.create_node(leaf)
        count = run_condensation_pass(db, leaf_threshold=50)
        assert count == 1

    def test_run_full_maintenance(self, db, sample_branch):
        # Create low-importance old node
        old_node = Node(importance=0.05)
        old_time = (
            datetime.now(timezone.utc) - timedelta(days=60)
        ).isoformat()
        old_node.last_accessed = old_time
        db.create_node(old_node)

        # Create enough leaves for condensation
        for i in range(55):
            leaf = Node(
                type=NodeType.LEAF,
                parent_id=sample_branch.node_id,
                title=f"leaf {i}",
            )
            db.create_node(leaf)

        report = run_full_maintenance(
            db,
            archive_threshold=0.1,
            archive_days=30,
            decay_rate=0.05,
            leaf_threshold=50,
        )
        assert "decayed" in report
        assert "archived" in report
        assert "condensed" in report
        assert report["archived"] >= 1
        assert report["condensed"] == 1


# ═════════════════════════════════════════════════════════════════════════
# Migration tests
# ═════════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_parse_obsidian_frontmatter_empty(self):
        content = "Just some text."
        metadata, body = parse_obsidian_frontmatter(content)
        assert metadata == {}
        assert body == "Just some text."

    def test_parse_obsidian_frontmatter_with_metadata(self):
        content = "---\ntitle: My Note\ntags: project, ai\nimportance: 8\n---\n\nBody content here."
        metadata, body = parse_obsidian_frontmatter(content)
        assert metadata["title"] == "My Note"
        assert metadata["importance"] == "8"
        assert "Body content here" in body

    def test_parse_obsidian_frontmatter_unclosed(self):
        content = "---\ntitle: Broken"
        metadata, body = parse_obsidian_frontmatter(content)
        assert metadata == {}
        assert body == content

    def test_extract_obsidian_links(self):
        content = "See [[Project Alpha]] and [[Note 2]] for details."
        links = extract_obsidian_links(content)
        assert "Project Alpha" in links
        assert "Note 2" in links
        assert len(links) == 2

    def test_extract_obsidian_links_no_links(self):
        assert extract_obsidian_links("No links here.") == []

    def test_extract_tags_from_content(self):
        content = "This is a #test and also #another-tag and #nested/tag"
        tags = extract_tags_from_content(content)
        assert "test" in tags
        assert "another-tag" in tags
        assert "nested/tag" in tags

    def test_extract_tags_no_tags(self):
        assert extract_tags_from_content("No tags here.") == []

    def test_scan_vault_nonexistent(self):
        with pytest.raises(NotADirectoryError):
            scan_vault("/nonexistent/path")

    def test_migrate_from_obsidian(self, db, tmp_path):
        # Create a mock Obsidian vault
        vault = tmp_path / "my_vault"
        vault.mkdir()
        (vault / "Note 1.md").write_text("---\ntitle: First Note\nimportance: 7\n---\n\nContent of first note.")
        (vault / "Note 2.md").write_text("---\ntitle: Second Note\n---\n\nContent referencing [[First Note]].")
        sub = vault / "Projects"
        sub.mkdir()
        (sub / "Sub Note.md").write_text("---\ntitle: Sub\n---\n\nSub content.")

        report = migrate_from_obsidian(db, str(vault))
        assert report.nodes_created >= 4  # vault branch + directories + 3 notes
        assert report.edges_created >= 1  # wiki-link edge
        assert report.files_failed == 0

        # Verify nodes exist
        notes = db.list_nodes(type_filter=NodeType.LEAF)
        titles = [n.title for n in notes]
        assert "First Note" in titles
        assert "Second Note" in titles
        assert "Sub" in titles

        # Verify edges
        edge_count = db.count_edges()
        assert edge_count >= 1

    def test_migration_report_str(self):
        report = MigrationReport(
            vault_path="/test",
            nodes_created=10,
            edges_created=3,
            files_failed=0,
        )
        assert "10 nodes" in str(report)
        assert "3 edges" in str(report)

    def test_migration_report_with_failures(self):
        report = MigrationReport(
            vault_path="/test",
            nodes_created=5,
            edges_created=1,
            files_failed=2,
        )
        assert "2 files failed" in str(report)

    def test_migrate_with_root_node_id(self, db, tmp_path, sample_root):
        vault = tmp_path / "subvault"
        vault.mkdir()
        (vault / "test.md").write_text("---\ntitle: Test\n---\n\nContent.")
        report = migrate_from_obsidian(
            db, str(vault), root_node_id=sample_root.node_id
        )
        assert report.nodes_created >= 2  # root already existed, just the leaf created


# ═════════════════════════════════════════════════════════════════════════
# Integration tests
# ═════════════════════════════════════════════════════════════════════════


class TestIntegration:
    def test_full_lifecycle(self, db):
        """End-to-end: create root, branches, leaves, add edges, prune."""
        # Create root
        root = Node(type=NodeType.ROOT, title="Vega", importance=1.0)
        root_id = db.create_node(root)

        # Create branches
        branch1 = Node(
            type=NodeType.BRANCH,
            parent_id=root_id,
            title="Work",
            importance=0.9,
        )
        branch1_id = db.create_node(branch1)

        branch2 = Node(
            type=NodeType.BRANCH,
            parent_id=root_id,
            title="Personal",
            importance=0.7,
        )
        branch2_id = db.create_node(branch2)

        # Create leaves
        leaf1 = Node(
            type=NodeType.LEAF,
            parent_id=branch1_id,
            title="Project Report",
            content="Q1 results are in.",
            importance=0.8,
        )
        leaf1_id = db.create_node(leaf1)

        leaf2 = Node(
            type=NodeType.LEAF,
            parent_id=branch2_id,
            title="Grocery List",
            content="Milk, eggs, bread.",
            importance=0.3,
        )
        leaf2_id = db.create_node(leaf2)

        # Add an edge
        edge = Edge(
            source_id=leaf1_id,
            target_id=leaf2_id,
            relationship=RelationshipType.REFERENCES,
            strength=0.7,
        )
        db.create_edge(edge)

        # Verify counts
        assert db.count_nodes() == 5
        assert db.count_edges() == 1

        # Search
        results = db.search_nodes("Project")
        assert len(results) == 1

        # Reinforce
        reinforce_node(db, leaf2_id, boost=0.5)
        fetched = db.get_node(leaf2_id)
        assert fetched.importance == 0.8

        # Archive check
        archivable = get_archivable_nodes(db, importance_threshold=0.1, days_unused=0)
        assert len(archivable) == 0  # all importance >= 0.3

        # Decay importance
        apply_importance_decay(db, decay_rate=0.5, weeks=1.0)
        fetched = db.get_node(leaf2_id)
        assert fetched.importance == 0.4

        # Delete
        db.delete_node(leaf2_id)
        assert db.count_nodes() == 4

    def test_default_db_path(self):
        """Test that the default db path uses VEGA_CONTEXT_DB env var."""
        import os
        old_val = os.environ.get("VEGA_CONTEXT_DB")
        os.environ["VEGA_CONTEXT_DB"] = "/tmp/test_vega_ctx.db"
        try:
            db = ContextTreeDB()
            assert db.db_path == "/tmp/test_vega_ctx.db"
            db.close()
        finally:
            if old_val is None:
                del os.environ["VEGA_CONTEXT_DB"]
            else:
                os.environ["VEGA_CONTEXT_DB"] = old_val
            if os.path.exists("/tmp/test_vega_ctx.db"):
                os.unlink("/tmp/test_vega_ctx.db")


class TestEdgeEquality:
    def test_edge_same_content(self):
        e1 = Edge(
            source_id="a",
            target_id="b",
            relationship=RelationshipType.EXTENDS,
            strength=0.9,
        )
        e2 = Edge(
            source_id="a",
            target_id="b",
            relationship=RelationshipType.EXTENDS,
            strength=0.9,
        )
        # Note: edges are NOT value objects (IDs differ) — this is expected
        assert e1.edge_id != e2.edge_id
        assert e1.source_id == e2.source_id
        assert e1.target_id == e2.target_id