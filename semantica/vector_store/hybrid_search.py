"""
Hybrid Search Module

This module provides hybrid search capabilities combining vector similarity search
and metadata filtering for enhanced retrieval in the Semantica framework, supporting
result fusion, ranking strategies, and multi-source search.

Key Features:
    - Combined vector similarity and metadata filtering
    - Multiple ranking strategies (RRF, Weighted Average)
    - Metadata filter builder with various operators
    - Multi-source search and result fusion
    - Configurable ranking parameters
    - Performance optimization

Main Classes:
    - HybridSearch: Main hybrid search coordinator
    - MetadataFilter: Metadata filter builder with condition chaining
    - SearchRanker: Result ranking and fusion strategies

Example Usage:
    >>> from semantica.vector_store import HybridSearch, MetadataFilter
    >>> search = HybridSearch()
    >>> filter = MetadataFilter().eq("category", "science").gt("year", 2020)
    >>> results = search.search(query_vector, vectors, metadata, vector_ids, filter=filter, k=10)
    >>> 
    >>> from semantica.vector_store import SearchRanker
    >>> ranker = SearchRanker(strategy="reciprocal_rank_fusion")
    >>> fused = ranker.rank([results1, results2], k=60)
    >>> 
    >>> sources = [{"vectors": v1, "metadata": m1, "ids": ids1}, {"vectors": v2, "metadata": m2, "ids": ids2}]
    >>> results = search.multi_source_search(query_vector, sources, k=10)

Author: Semantica Contributors
License: MIT
"""

from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


class MetadataFilter:
    """Metadata filter builder."""

    def __init__(self):
        """Initialize metadata filter."""
        self.conditions: List[Dict[str, Any]] = []

    def add_condition(self, field: str, operator: str, value: Any) -> "MetadataFilter":
        """
        Add filter condition.

        Args:
            field: Field name
            operator: Operator ("eq", "ne", "gt", "gte", "lt", "lte", "in", "contains")
            value: Value to filter by

        Returns:
            Self for chaining
        """
        self.conditions.append({"field": field, "operator": operator, "value": value})
        return self

    def eq(self, field: str, value: Any) -> "MetadataFilter":
        """Add equality condition."""
        return self.add_condition(field, "eq", value)

    def ne(self, field: str, value: Any) -> "MetadataFilter":
        """Add not-equal condition."""
        return self.add_condition(field, "ne", value)

    def gt(self, field: str, value: Any) -> "MetadataFilter":
        """Add greater-than condition."""
        return self.add_condition(field, "gt", value)

    def gte(self, field: str, value: Any) -> "MetadataFilter":
        """Add greater-than-or-equal condition."""
        return self.add_condition(field, "gte", value)

    def lt(self, field: str, value: Any) -> "MetadataFilter":
        """Add less-than condition."""
        return self.add_condition(field, "lt", value)

    def lte(self, field: str, value: Any) -> "MetadataFilter":
        """Add less-than-or-equal condition."""
        return self.add_condition(field, "lte", value)

    def contains(self, field: str, value: Any) -> "MetadataFilter":
        """Add contains condition."""
        return self.add_condition(field, "contains", value)

    def in_list(self, field: str, values: List[Any]) -> "MetadataFilter":
        """Add in-list condition."""
        return self.add_condition(field, "in", values)

    def matches(self, metadata: Dict[str, Any]) -> bool:
        """Check if metadata matches all conditions."""
        for condition in self.conditions:
            field = condition["field"]
            operator = condition["operator"]
            value = condition["value"]

            if field not in metadata:
                return False

            field_value = metadata[field]

            if operator == "eq" and field_value != value:
                return False
            elif operator == "ne" and field_value == value:
                return False
            elif operator == "gt" and not (field_value > value):
                return False
            elif operator == "gte" and not (field_value >= value):
                return False
            elif operator == "lt" and not (field_value < value):
                return False
            elif operator == "lte" and not (field_value <= value):
                return False
            elif operator == "contains":
                if isinstance(field_value, str) and isinstance(value, str):
                    if value not in field_value:
                        return False
                elif isinstance(field_value, list):
                    if value not in field_value:
                        return False
                else:
                    return False
            elif operator == "in" and field_value not in value:
                return False

        return True


class SearchRanker:
    """Search result ranker."""

    def __init__(self, strategy: str = "reciprocal_rank_fusion"):
        """Initialize search ranker."""
        self.strategy = strategy
        self.logger = get_logger("search_ranker")

    def reciprocal_rank_fusion(
        self, results: List[List[Dict[str, Any]]], k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion (RRF) algorithm.

        Args:
            results: List of result lists from different sources
            k: RRF constant

        Returns:
            Fused and ranked results
        """
        scores: Dict[str, float] = {}

        for result_list in results:
            for rank, result in enumerate(result_list, start=1):
                result_id = result.get("id", str(id(result)))
                score = 1.0 / (k + rank)
                scores[result_id] = scores.get(result_id, 0.0) + score

        # Sort by score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Reconstruct results
        fused_results = []
        result_map = {}
        for result_list in results:
            for result in result_list:
                result_id = result.get("id", str(id(result)))
                result_map[result_id] = result

        for result_id, score in ranked:
            if result_id in result_map:
                result = result_map[result_id].copy()
                result["score"] = score
                fused_results.append(result)

        return fused_results

    def weighted_average(
        self, results: List[List[Dict[str, Any]]], weights: List[float]
    ) -> List[Dict[str, Any]]:
        """
        Weighted average fusion.

        Args:
            results: List of result lists
            weights: Weights for each result list

        Returns:
            Fused results
        """
        if len(weights) != len(results):
            weights = [1.0 / len(results)] * len(results)

        scores: Dict[str, Tuple[float, Dict[str, Any]]] = {}

        for weight, result_list in zip(weights, results):
            for result in result_list:
                result_id = result.get("id", str(id(result)))
                score = result.get("score", 0.0) * weight

                if result_id not in scores:
                    scores[result_id] = (0.0, result)

                scores[result_id] = (scores[result_id][0] + score, scores[result_id][1])

        # Sort by score
        ranked = sorted(scores.values(), key=lambda x: x[0], reverse=True)

        fused_results = []
        for score, result in ranked:
            result_copy = result.copy()
            result_copy["score"] = score
            fused_results.append(result_copy)

        return fused_results

    def rank(
        self, results: List[List[Dict[str, Any]]], **options
    ) -> List[Dict[str, Any]]:
        """
        Rank and fuse results.

        Args:
            results: List of result lists
            **options: Ranking options

        Returns:
            Fused and ranked results
        """
        if self.strategy == "reciprocal_rank_fusion":
            k = options.get("k", 60)
            return self.reciprocal_rank_fusion(results, k)
        elif self.strategy == "weighted_average":
            weights = options.get("weights", [1.0 / len(results)] * len(results))
            return self.weighted_average(results, weights)
        else:
            return self.reciprocal_rank_fusion(results)


class HybridSearch:
    """
    Hybrid search combining vector similarity and metadata filtering.

    • Vector similarity search
    • Metadata filtering and querying
    • Result fusion and ranking
    • Performance optimization
    • Error handling and recovery
    • Advanced search strategies
    """

    def __init__(self, vector_store=None, **config):
        """Initialize hybrid search."""
        self.logger = get_logger("hybrid_search")
        self.config = config
        self.vector_store = vector_store
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True
        self.ranker = SearchRanker(
            config.get("ranking_strategy", "reciprocal_rank_fusion")
        )
        self.embedding_generator = None

    def search(
        self,
        query: Union[str, np.ndarray],
        vectors: Optional[List[np.ndarray]] = None,
        metadata: Optional[List[Dict[str, Any]]] = None,
        vector_ids: Optional[List[str]] = None,
        k: int = 10,
        metadata_filter: Optional[MetadataFilter] = None,
        **options,
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search.

        Args:
            query: Query vector or string
            vectors: List of vectors to search (optional if vector_store provided)
            metadata: List of metadata dictionaries (optional if vector_store provided)
            vector_ids: Vector IDs (optional if vector_store provided)
            k: Number of results
            metadata_filter: Optional metadata filter
            **options: Additional options

        Returns:
            List of search results
        """
        # Handle legacy argument top_k. Must be popped, not just read: it's
        # later forwarded via **options to VectorStore.search_vectors(),
        # which itself passes an explicit top_k=k to some backends (e.g.
        # sqlite, pgvector) — a leftover 'top_k' in options collides with
        # that and raises "got multiple values for keyword argument".
        if "top_k" in options:
            k = options.pop("top_k")
        # query_vector is derived from `query` above; drop any stray value
        # passed in **options so it doesn't collide with that derivation.
        # (**options is a fresh dict per call, so this can't affect the caller.)
        if "query_vector" in options:
            self.logger.debug(
                "Ignoring 'query_vector' passed in options; it is derived from 'query' instead."
            )
            options.pop("query_vector")

        tracking_id = self.progress_tracker.start_tracking(
            module="vector_store",
            submodule="HybridSearch",
            message=f"Performing hybrid search for {k} results",
        )

        try:
            # Resolve the query vector first: it's needed both for local
            # search below and for the backend-delegated path.
            if isinstance(query, str):
                self.progress_tracker.update_tracking(
                    tracking_id, message="Generating query embedding..."
                )
                if not self.embedding_generator:
                    try:
                        from ..embeddings import EmbeddingGenerator
                        self.embedding_generator = EmbeddingGenerator()
                    except (ImportError, OSError):
                        raise ImportError("EmbeddingGenerator not available for string queries")

                query_vector = self.embedding_generator.generate_embeddings(query, data_type="text")
                # Handle if it returns batch (2D) or single (1D)
                if len(query_vector.shape) == 2:
                     query_vector = query_vector[0]
            else:
                # Backend stores (e.g. FAISSStore.search_similar) assume an
                # ndarray and call .ndim on it, so normalize list input here
                # rather than relying on _vector_search's own conversion,
                # which the backend-delegated path below bypasses.
                query_vector = np.asarray(query) if isinstance(query, list) else query

            # Resolve vector store data if not provided
            if vectors is None and self.vector_store:
                if getattr(self.vector_store, "backend", None) == "inmemory":
                    # In-memory backend: read corpus directly from the local dicts.
                    # We must NOT use this path for persistent backends (faiss,
                    # weaviate, qdrant, milvus, pgvector, sqlite) even though
                    # self.vector_store.vectors now exists as a mirror — the mirror
                    # only reflects writes made through the facade in the current
                    # session and would miss pre-existing backend data entirely.
                    vector_ids = list(self.vector_store.vectors.keys())
                    vectors = [self.vector_store.vectors[vid] for vid in vector_ids]
                    metadata = [self.vector_store.metadata.get(vid, {}) for vid in vector_ids]
                else:
                    # Backend-agnostic path: all persistent backends (faiss, weaviate,
                    # qdrant, milvus, pinecone, pgvector, sqlite) must go through the
                    # store's public search API to cover the full index, including
                    # data that predates the current session or was written externally.
                    self.progress_tracker.update_tracking(
                        tracking_id, message="Performing vector similarity search..."
                    )
                    fetch_k = k * (4 if metadata_filter else 2)
                    backend_results = self.vector_store.search_vectors(
                        query_vector=query_vector, k=fetch_k, **options
                    )

                    if metadata_filter:
                        self.progress_tracker.update_tracking(
                            tracking_id, message="Filtering by metadata..."
                        )
                        backend_results = [
                            result
                            for result in backend_results
                            if metadata_filter.matches(result.get("metadata", {}))
                        ]

                    # Normalize to the same result schema the local search
                    # path produces, since backends don't all return the
                    # same set of keys. Unlike the local path (which always
                    # knows distance = 1.0 - cosine_similarity), backends use
                    # different metrics (L2, inner product, cosine, ...), so
                    # a missing distance is left as None rather than guessed
                    # from score — assuming cosine semantics would produce
                    # nonsensical values for e.g. raw L2 distances.
                    normalized_results = [
                        {
                            "id": result.get("id"),
                            "score": result.get("score", 0.0),
                            "distance": result.get("distance"),
                            "metadata": result.get("metadata", {}),
                        }
                        for result in backend_results[:k]
                    ]

                    self.progress_tracker.stop_tracking(
                        tracking_id,
                        status="completed",
                        message=f"Hybrid search completed: {len(normalized_results)} results",
                    )
                    return normalized_results

            if vectors is None:
                vectors = []
            if metadata is None:
                metadata = []
            if vector_ids is None:
                # IDs weren't provided alongside explicit vectors/metadata;
                # generate stable positional ones so downstream indexing
                # (e.g. filtered_ids[i], _vector_search's vector_ids[idx])
                # doesn't operate on None.
                vector_ids = [f"vec_{i}" for i in range(len(vectors))]

            # Check if vectors/metadata are empty
            # Handle both list and numpy array cases safely
            if len(vectors) == 0 or len(metadata) == 0:
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message="No vectors or metadata to search",
                )
                return []

            # Filter by metadata first
            if metadata_filter:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Filtering by metadata..."
                )
                filtered_indices = [
                    i
                    for i, meta in enumerate(metadata)
                    if metadata_filter.matches(meta)
                ]

                filtered_vectors = [vectors[i] for i in filtered_indices]
                filtered_metadata = [metadata[i] for i in filtered_indices]
                filtered_ids = [vector_ids[i] for i in filtered_indices]
            else:
                filtered_vectors = vectors
                filtered_metadata = metadata
                filtered_ids = vector_ids

            if len(filtered_vectors) == 0:
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message="No vectors after filtering",
                )
                return []

            # Perform vector similarity search
            self.progress_tracker.update_tracking(
                tracking_id, message="Performing vector similarity search..."
            )
            vector_results = self._vector_search(
                query_vector,
                filtered_vectors,
                filtered_ids,
                k * 2,  # Get more results for ranking
                **options,
            )

            # Add metadata to results
            self.progress_tracker.update_tracking(
                tracking_id, message="Adding metadata to results..."
            )
            for result in vector_results:
                result_id = result.get("id")
                if result_id in filtered_ids:
                    idx = filtered_ids.index(result_id)
                    result["metadata"] = filtered_metadata[idx]

            # Rank and return top k
            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Hybrid search completed: {len(vector_results[:k])} results",
            )
            return vector_results[:k]
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _vector_search(
        self,
        query_vector: np.ndarray,
        vectors: List[np.ndarray],
        vector_ids: List[str],
        k: int,
        **options,
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search."""
        if len(vectors) == 0:
            return []

        # Convert to numpy
        if isinstance(vectors[0], list):
            vectors = np.array(vectors)
        else:
            vectors = np.vstack(vectors)

        if isinstance(query_vector, list):
            query_vector = np.array(query_vector)

        # Calculate cosine similarity
        query_norm = np.linalg.norm(query_vector)
        vector_norms = np.linalg.norm(vectors, axis=1)

        similarities = np.dot(vectors, query_vector) / (
            vector_norms * query_norm + 1e-8
        )

        # Get top k
        top_indices = np.argsort(similarities)[::-1][:k]

        results = []
        for idx in top_indices:
            results.append(
                {
                    "id": vector_ids[idx],
                    "score": float(similarities[idx]),
                    "distance": 1.0 - float(similarities[idx]),
                }
            )

        return results

    def multi_source_search(
        self,
        query_vector: np.ndarray,
        sources: List[Dict[str, Any]],
        k: int = 10,
        **options,
    ) -> List[Dict[str, Any]]:
        """
        Search across multiple sources and fuse results.

        Args:
            query_vector: Query vector
            sources: List of source dictionaries with 'vectors', 'metadata', 'ids'
            k: Number of results
            **options: Additional options

        Returns:
            Fused search results
        """
        all_results = []

        for source in sources:
            source_results = self.search(
                query_vector,
                source.get("vectors", []),
                source.get("metadata", []),
                source.get("ids", []),
                k=k,
                metadata_filter=source.get("filter"),
                **options,
            )
            all_results.append(source_results)

        # Fuse results using ranker
        fused_results = self.ranker.rank(all_results, **options)

        return fused_results[:k]

    def filter_by_metadata(
        self, results: List[Dict[str, Any]], metadata_filter: MetadataFilter
    ) -> List[Dict[str, Any]]:
        """
        Filter results by metadata.

        Args:
            results: Search results
            metadata_filter: Metadata filter

        Returns:
            Filtered results
        """
        filtered = []
        for result in results:
            metadata = result.get("metadata", {})
            if metadata_filter.matches(metadata):
                filtered.append(result)

        return filtered
