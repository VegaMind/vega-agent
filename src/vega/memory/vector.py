"""ChromaDB vector-store wrapper for Vega's memory subsystem.

Two collections:

* ``vega_memories`` — general semantic recall (long-term facts, notes, observations).
* ``vega_episodic`` — recent interactions, conversation snippets, short-term context.

Uses ChromaDB's default all-MiniLM-L6-v2 sentence transformer embedder
(``all-MiniLM-L6-v2``), producing 384-dimensional embeddings stored
locally under ``~/.vega/chromadb/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COLLECTION_MEMORIES = "vega_memories"
"""General-purpose semantic recall collection."""

COLLECTION_EPISODIC = "vega_episodic"
"""Short-term / recent-interaction collection."""

DEFAULT_COLLECTIONS = (COLLECTION_MEMORIES, COLLECTION_EPISODIC)

def _default_persist_dir() -> Path:
    """Return the default ChromaDB persist directory (computed lazily)."""
    return Path.home() / ".vega" / "chromadb"


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------


class MemoryStore:
    """ChromaDB wrapper providing ``store``, ``search``, ``delete``, and
    ``list_collections`` for Vega's two memory collections.

    Attributes:
        persist_dir: Directory where ChromaDB stores its data.
        client: The underlying ``chromadb.PersistentClient``.
        collections: Dict of ``{name: Collection}`` for the two built-in
            collections (lazily created on first access).
    """

    def __init__(self, persist_dir: Optional[Path | str] = None) -> None:
        """Initialise the ChromaDB client and ensure the two collections
        exist.

        Args:
            persist_dir: On-disk directory for ChromaDB data.  Defaults to
                ``~/.vega/chromadb/``.
        """
        self.persist_dir = Path(persist_dir).expanduser() if persist_dir else _default_persist_dir()
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collections: Dict[str, chromadb.Collection] = {}
        self._ensure_collections()

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def _ensure_collections(self) -> None:
        """Get or create the two built-in collections, creating them if they don't exist."""
        for name in DEFAULT_COLLECTIONS:
            try:
                col = self.client.get_collection(name)
            except Exception:
                col = self.client.create_collection(
                    name,
                    metadata={"description": f"Vega collection: {name}"},
                )
            self._collections[name] = col

    def _collection(self, name: str) -> chromadb.Collection:
        """Return the collection *name*, raising ``ValueError`` if unknown.

        Args:
            name: Collection name.

        Returns:
            The ChromaDB ``Collection``.

        Raises:
            ValueError: If *name* is not one of the known collections.
        """
        if name not in self._collections:
            raise ValueError(
                f"Unknown collection {name!r}. "
                f"Available: {list(self._collections)}"
            )
        return self._collections[name]

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """Get an existing collection or create a new one.

        This is the public method for creating custom collections beyond the
        two built-in ones.

        Args:
            name: Collection name.

        Returns:
            The ChromaDB ``Collection``.
        """
        if name in self._collections:
            return self._collections[name]
        try:
            col = self.client.get_collection(name)
        except Exception:
            col = self.client.create_collection(
                name,
                metadata={"description": f"Vega collection: {name}"},
            )
        self._collections[name] = col
        return col

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def store(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        collection: str = COLLECTION_MEMORIES,
        doc_id: Optional[str] = None,
    ) -> str:
        """Store a text entry as a vector embedding.

        Args:
            text: The text content to embed and store.
            metadata: Optional dict of metadata to associate with the entry
                (e.g. ``{"source": "user-input", "timestamp": "..."}``).
            collection: Target collection name (default ``vega_memories``).
            doc_id: Optional explicit document ID.  Auto-generated (UUID-like)
                if omitted.

        Returns:
            The document ID of the stored entry.
        """
        col = self._collection(collection)
        _id = doc_id or _make_id()
        col.add(
            documents=[text],
            metadatas=[metadata] if metadata else None,
            ids=[_id],
        )
        return _id

    def search(
        self,
        query: str,
        n_results: int = 5,
        collection: str = COLLECTION_MEMORIES,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for entries semantically similar to *query*.

        Args:
            query: Natural-language query string.
            n_results: Maximum number of results to return (default 5).
            collection: Collection to search (default ``vega_memories``).
            where: Optional metadata filter dict (e.g. ``{"source": "obsidian"}``).

        Returns:
            A list of dicts, each with keys ``id``, ``document``, ``metadata``,
            and ``distance``.
        """
        col = self._collection(collection)
        results = col.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )

        output: List[Dict[str, Any]] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            output.append(
                {
                    "id": ids[i],
                    "document": docs[i] if docs else None,
                    "metadata": metas[i] if metas else {},
                    "distance": dists[i] if dists else None,
                }
            )
        return output

    def delete(
        self,
        ids: Optional[List[str]] = None,
        collection: str = COLLECTION_MEMORIES,
        where: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Delete entries from a collection by ID or metadata filter.

        Args:
            ids: List of document IDs to delete.
            collection: Collection name (default ``vega_memories``).
            where: Metadata filter to select entries for deletion
                (e.g. ``{"source": "obsidian"}``).  Mutually exclusive with
                *ids* — if both are provided, *ids* takes precedence.

        Returns:
            The number of deleted entries (best-effort estimate).
        """
        col = self._collection(collection)
        if ids:
            col.delete(ids=ids)
            return len(ids)
        if where:
            # ChromaDB delete doesn't support `where` directly in all versions,
            # so we search first then delete by ID.
            results = col.get(where=where)
            found_ids = results.get("ids", [])
            if found_ids:
                col.delete(ids=found_ids)
            return len(found_ids)
        return 0

    def list_collections(self) -> List[Dict[str, Any]]:
        """List all collections known to this ChromaDB instance.

        Returns:
            A list of dicts with keys ``name`` and ``count`` (document count).
        """
        collections = self.client.list_collections()
        result = []
        for col in collections:
            try:
                count = col.count()
            except Exception:
                count = 0
            result.append({"name": col.name, "count": count})
        return result

    def count(self, collection: str = COLLECTION_MEMORIES) -> int:
        """Return the number of documents in a collection.

        Args:
            collection: Collection name (default ``vega_memories``).

        Returns:
            Document count.
        """
        return self._collection(collection).count()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_id() -> str:
    """Generate a short, reasonably unique document ID."""
    import uuid
    return uuid.uuid4().hex[:16]