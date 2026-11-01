"""
Shared graph session — lazy singleton across all tool handlers.

The graph is initialised once on first access and shared for the
lifetime of the MCP server process.  Set SEMANTICA_KG_PATH to
automatically load a persisted graph on start.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("semantica.mcp.session")

# Backends the retrieval tools can actually support end to end.  faiss
# and pgvector have no metadata-scoped delete, so update_document and
# remove_document cannot work on them; selecting them fails fast here
# instead of blowing up mid-update.
SUPPORTED_VECTOR_BACKENDS = ("inmemory", "sqlite")

_graph: Optional[Any] = None
_embedder: Optional[Any] = None
_vector_store: Optional[Any] = None

# Tracks whether the last graph initialisation successfully loaded the
# configured SEMANTICA_KG_PATH file.  When True (or no path was configured)
# mutation handlers are allowed to save.  When False an existing file failed
# to load; saving would overwrite the original data with an empty graph, so
# persistence is blocked until the process is restarted with a readable file.
_load_ok: bool = True


def get_graph() -> Any:
    """
    Return the shared ContextGraph instance, creating it on first call.

    The graph is created with advanced_analytics=True so all centrality,
    community-detection, and embedding features are available.
    """
    global _graph, _load_ok
    if _graph is None:
        from semantica.context import ContextGraph

        _graph = ContextGraph(advanced_analytics=True)
        _load_ok = True  # default: safe to persist

        path = kg_file_to_load()
        if path:
            try:
                _graph.load_from_file(path)
                log.info("Graph loaded from %s", path)
            except Exception as exc:
                log.warning(
                    "Could not load graph from %s: %s — persistence disabled "
                    "to protect existing data; restart the server to retry.",
                    path, exc,
                )
                _load_ok = False  # do not overwrite the original file

    return _graph


def kg_path() -> str:
    """Return the configured ``SEMANTICA_KG_PATH``, or ``""`` when unset."""
    return os.environ.get("SEMANTICA_KG_PATH", "").strip()


def kg_file_to_load() -> Optional[str]:
    """Return the graph file ``get_graph`` will load, or None to start empty.

    A missing file starts an empty graph that is created on the first save.
    An empty file means the path was just created (e.g. a fresh tempfile)
    and is likewise treated as "start with empty graph" rather than a
    corrupt-file failure.  Shared with ``semantica doctor`` so its check
    follows the same rules as the server (#1818).
    """
    path = kg_path()
    if path and os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    return None


def get_embedder() -> Any:
    """
    Return the shared EmbeddingGenerator instance, creating it on first call.

    Used by the semantic retrieval tools (#1235) to embed documents and
    queries with one consistent model, so stored vectors and query
    vectors always share the same dimensionality.
    """
    global _embedder
    if _embedder is None:
        from semantica.embeddings import EmbeddingGenerator

        _embedder = EmbeddingGenerator()
        log.info(
            "Embedding generator initialised (method=%s)",
            _embedder.get_text_method(),
        )
    return _embedder


def resolve_vector_backend() -> Tuple[str, Dict[str, Any]]:
    """Return the backend and store config ``get_vector_store`` will use.

    Reads and validates the environment without building a store or an
    embedder, so ``semantica doctor`` can report exactly what this server
    would do instead of re-implementing the rules (#1818).  The returned
    config does not yet include ``dimension``, which comes from the embedder.

    Raises:
        ValueError: The backend is unsupported, or ``sqlite`` is selected
            without ``SEMANTICA_VECTOR_DB_PATH``.
    """
    backend = os.environ.get("SEMANTICA_VECTOR_BACKEND", "inmemory").strip().lower()
    if backend not in SUPPORTED_VECTOR_BACKENDS:
        raise ValueError(
            f"SEMANTICA_VECTOR_BACKEND={backend!r} is not supported by the "
            "MCP retrieval tools; supported backends: "
            + ", ".join(SUPPORTED_VECTOR_BACKENDS)
        )
    config: Dict[str, Any] = {}
    if backend == "sqlite":
        db_path = os.environ.get("SEMANTICA_VECTOR_DB_PATH", "").strip()
        if not db_path:
            raise ValueError(
                "SEMANTICA_VECTOR_BACKEND=sqlite requires "
                "SEMANTICA_VECTOR_DB_PATH to point at the database file"
            )
        config["db_path"] = db_path
    return backend, config


def get_vector_store() -> Any:
    """
    Return the shared VectorStore instance, creating it on first call.

    Backend selection:

    • ``SEMANTICA_VECTOR_BACKEND`` — ``inmemory`` (default) or ``sqlite``.
      The ``sqlite`` backend additionally requires
      ``SEMANTICA_VECTOR_DB_PATH``.  Other VectorStore backends (faiss,
      pgvector) are rejected: they lack the metadata-scoped delete the
      update/remove tools need.
    • ``SEMANTICA_VECTOR_PATH`` — a *directory* previously written by
      ``VectorStore.save()``.  If it exists, the store is loaded from it
      on start.  Note this is a directory, unlike SEMANTICA_KG_PATH which
      is a single JSON file.  The persisted dimension must match the
      active embedder or startup fails — otherwise queries would either
      error on shape mismatch or silently rank across incompatible
      embedding spaces.
    """
    global _vector_store
    if _vector_store is None:
        from semantica.vector_store import VectorStore

        backend, config = resolve_vector_backend()
        # VectorStore defaults to dimension 768, which does not match the
        # default embedding model (all-MiniLM-L6-v2 = 384, hash fallback
        # = 128).  Always derive it from the embedder so store and
        # queries stay consistent.
        embedder = get_embedder()
        config["dimension"] = embedder.text_embedder.get_embedding_dimension()

        store = VectorStore(backend=backend, config=config)

        vector_path = os.environ.get("SEMANTICA_VECTOR_PATH", "").strip()
        if vector_path and os.path.isdir(vector_path):
            try:
                store.load(vector_path)
                log.info("Vector store loaded from %s", vector_path)
            except Exception as exc:
                raise ValueError(
                    f"Could not load vector store from {vector_path}: {exc}"
                ) from exc
            loaded_dim = getattr(store, "dimension", None)
            if loaded_dim and loaded_dim != config["dimension"]:
                raise ValueError(
                    f"Persisted vector store at {vector_path} has dimension "
                    f"{loaded_dim}, but the active embedder produces "
                    f"{config['dimension']}. Re-embed the corpus or point "
                    "SEMANTICA_VECTOR_PATH at a store built with the same model."
                )

        _vector_store = store
        log.info("Vector store initialised (backend=%s)", backend)
    return _vector_store


def reset_vector_store() -> None:
    """Reset the vector store singleton (mainly useful in tests)."""
    global _vector_store
    _vector_store = None


def is_persistence_safe() -> bool:
    """Return True when it is safe to write mutations back to SEMANTICA_KG_PATH.

    Returns False after a failed load so that mutation handlers do not
    overwrite the original (possibly intact) file with a fresh empty graph.
    """
    return _load_ok


def reset_graph() -> None:
    """Reset the singleton (mainly useful in tests)."""
    global _graph, _load_ok
    _graph = None
    _load_ok = True
