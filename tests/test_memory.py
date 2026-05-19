"""Tests for the Vega memory subsystem (``vega.memory.vector``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vega.memory import MemoryStore
from vega.memory.vector import (
    COLLECTION_EPISODIC,
    COLLECTION_MEMORIES,
    DEFAULT_COLLECTIONS,
    _make_id,
)


# ═════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mem_store(tmp_path: Path) -> MemoryStore:
    """Return a MemoryStore backed by a temporary directory."""
    return MemoryStore(persist_dir=tmp_path / "chromadb")


# ═════════════════════════════════════════════════════════════════════════
# Initialisation
# ═════════════════════════════════════════════════════════════════════════


class TestMemoryStoreInit:
    def test_default_persist_dir_creates(self, monkeypatch):
        """Default persist dir should be created on init."""
        import tempfile
        td = tempfile.mkdtemp()
        fake_home = Path(td)
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        store = MemoryStore()
        expected = fake_home / ".vega" / "chromadb"
        assert expected.is_dir()
        store.client.clear_system_cache()

    def test_custom_persist_dir(self, tmp_path: Path):
        """Custom persist dir should be created and used."""
        d = tmp_path / "my_chroma"
        store = MemoryStore(persist_dir=d)
        assert d.is_dir()
        store.client.clear_system_cache()

    def test_collections_created(self, mem_store: MemoryStore):
        """Both default collections should exist after init."""
        cols = {c["name"] for c in mem_store.list_collections()}
        assert COLLECTION_MEMORIES in cols
        assert COLLECTION_EPISODIC in cols

    def test_unknown_collection_raises(self, mem_store: MemoryStore):
        """Accessing an unknown collection should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown collection"):
            mem_store._collection("nonexistent")


# ═════════════════════════════════════════════════════════════════════════
# Store
# ═════════════════════════════════════════════════════════════════════════


class TestMemoryStoreStore:
    def test_store_and_count(self, mem_store: MemoryStore):
        """Storing text should increase the document count."""
        assert mem_store.count(COLLECTION_MEMORIES) == 0
        doc_id = mem_store.store("Hello, world!", collection=COLLECTION_MEMORIES)
        assert mem_store.count(COLLECTION_MEMORIES) == 1
        assert isinstance(doc_id, str)
        assert len(doc_id) > 0
        mem_store.client.clear_system_cache()

    def test_store_with_metadata(self, mem_store: MemoryStore):
        """Storing with metadata should persist it."""
        doc_id = mem_store.store(
            "Test memory",
            metadata={"source": "pytest", "importance": 0.8},
            collection=COLLECTION_MEMORIES,
        )
        results = mem_store.search("Test memory", n_results=10, collection=COLLECTION_MEMORIES)
        found = [r for r in results if r["id"] == doc_id]
        assert len(found) == 1
        assert found[0]["metadata"]["source"] == "pytest"
        assert found[0]["metadata"]["importance"] == 0.8
        mem_store.client.clear_system_cache()

    def test_store_custom_id(self, mem_store: MemoryStore):
        """Storing with an explicit ID should preserve it."""
        custom_id = "my-custom-id-42"
        mem_store.store("Custom ID test", doc_id=custom_id, collection=COLLECTION_MEMORIES)
        results = mem_store.search("custom", n_results=10, collection=COLLECTION_MEMORIES)
        found = [r for r in results if r["id"] == custom_id]
        assert len(found) == 1
        mem_store.client.clear_system_cache()

    def test_store_episodic(self, mem_store: MemoryStore):
        """Storing to the episodic collection should work."""
        doc_id = mem_store.store(
            "Recent conversation snippet",
            collection=COLLECTION_EPISODIC,
        )
        assert mem_store.count(COLLECTION_EPISODIC) == 1
        assert doc_id is not None
        mem_store.client.clear_system_cache()


# ═════════════════════════════════════════════════════════════════════════
# Search
# ═════════════════════════════════════════════════════════════════════════


class TestMemoryStoreSearch:
    def test_search_returns_results(self, mem_store: MemoryStore):
        """Searching for stored text should return results."""
        mem_store.store("The capital of France is Paris.", collection=COLLECTION_MEMORIES)
        mem_store.store("Python is a programming language.", collection=COLLECTION_MEMORIES)
        mem_store.store("The Eiffel Tower is in Paris.", collection=COLLECTION_MEMORIES)
        mem_store.client.clear_system_cache()

        results = mem_store.search("France Paris", n_results=5, collection=COLLECTION_MEMORIES)
        assert len(results) >= 1
        assert any("Paris" in r["document"] for r in results)

    def test_search_empty_collection(self, mem_store: MemoryStore):
        """Searching an empty collection should return empty list."""
        results = mem_store.search("anything", n_results=5, collection=COLLECTION_MEMORIES)
        assert results == []
        mem_store.client.clear_system_cache()

    def test_search_with_filter(self, mem_store: MemoryStore):
        """Search with a metadata filter should respect it."""
        mem_store.store("Important fact", metadata={"source": "book"}, collection=COLLECTION_MEMORIES)
        mem_store.store("Trivial fact", metadata={"source": "web"}, collection=COLLECTION_MEMORIES)
        mem_store.client.clear_system_cache()

        results = mem_store.search("fact", n_results=10, collection=COLLECTION_MEMORIES, where={"source": "book"})
        assert len(results) >= 1
        for r in results:
            assert r["metadata"]["source"] == "book"
        mem_store.client.clear_system_cache()

    def test_search_returns_distances(self, mem_store: MemoryStore):
        """Search results should include distance values."""
        mem_store.store("Machine learning is fascinating.", collection=COLLECTION_MEMORIES)
        mem_store.client.clear_system_cache()
        results = mem_store.search("machine learning", n_results=5, collection=COLLECTION_MEMORIES)
        if results:
            assert "distance" in results[0]
        mem_store.client.clear_system_cache()


# ═════════════════════════════════════════════════════════════════════════
# Delete
# ═════════════════════════════════════════════════════════════════════════


class TestMemoryStoreDelete:
    def test_delete_by_id(self, mem_store: MemoryStore):
        """Deleting by ID should remove the entry."""
        doc_id = mem_store.store("Delete me", collection=COLLECTION_MEMORIES)
        assert mem_store.count(COLLECTION_MEMORIES) == 1
        deleted = mem_store.delete(ids=[doc_id], collection=COLLECTION_MEMORIES)
        assert deleted == 1
        # Re-fetch to verify
        mem_store.client.clear_system_cache()
        results = mem_store.search("Delete me", n_results=10, collection=COLLECTION_MEMORIES)
        assert len(results) == 0

    def test_delete_by_where(self, mem_store: MemoryStore):
        """Deleting by metadata filter should remove matching entries."""
        mem_store.store("Keep this", metadata={"tag": "keep"}, collection=COLLECTION_MEMORIES)
        mem_store.store("Remove this", metadata={"tag": "remove"}, collection=COLLECTION_MEMORIES)
        mem_store.client.clear_system_cache()

        deleted = mem_store.delete(collection=COLLECTION_MEMORIES, where={"tag": "remove"})
        assert deleted >= 1

        mem_store.client.clear_system_cache()
        results = mem_store.search("this", n_results=10, collection=COLLECTION_MEMORIES)
        tags = [r["metadata"].get("tag") for r in results]
        assert "remove" not in tags
        assert "keep" in tags

    def test_delete_empty_noop(self, mem_store: MemoryStore):
        """Delete with no ids or where should be a no-op."""
        deleted = mem_store.delete(collection=COLLECTION_MEMORIES)
        assert deleted == 0


# ═════════════════════════════════════════════════════════════════════════
# Collections
# ═════════════════════════════════════════════════════════════════════════


class TestMemoryStoreCollections:
    def test_list_collections(self, mem_store: MemoryStore):
        """list_collections should return both default collections."""
        cols = mem_store.list_collections()
        names = {c["name"] for c in cols}
        assert COLLECTION_MEMORIES in names
        assert COLLECTION_EPISODIC in names

    def test_get_or_create_new(self, mem_store: MemoryStore):
        """get_or_create_collection should create a new collection."""
        col = mem_store.get_or_create_collection("my_custom_collection")
        assert col.name == "my_custom_collection"
        cols = {c["name"] for c in mem_store.list_collections()}
        assert "my_custom_collection" in cols
        # Calling again should return the same collection
        col2 = mem_store.get_or_create_collection("my_custom_collection")
        assert col2.name == col.name

    def test_count(self, mem_store: MemoryStore):
        """count should return correct document count."""
        assert mem_store.count(COLLECTION_MEMORIES) == 0
        mem_store.store("Doc 1", collection=COLLECTION_MEMORIES)
        mem_store.store("Doc 2", collection=COLLECTION_MEMORIES)
        mem_store.client.clear_system_cache()
        assert mem_store.count(COLLECTION_MEMORIES) == 2


# ═════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════


class TestHelpers:
    def test_make_id_format(self):
        """_make_id should produce a 16-char hex string."""
        id1 = _make_id()
        id2 = _make_id()
        assert len(id1) == 16
        assert id1 != id2
        assert all(c in "0123456789abcdef" for c in id1)

    def test_default_collections(self):
        """DEFAULT_COLLECTIONS should contain the two standard names."""
        assert COLLECTION_MEMORIES in DEFAULT_COLLECTIONS
        assert COLLECTION_EPISODIC in DEFAULT_COLLECTIONS
        assert len(DEFAULT_COLLECTIONS) == 2