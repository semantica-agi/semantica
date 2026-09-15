"""
Milvus Store Module

This module provides Milvus vector database integration for vector storage and
similarity search in the Semantica framework, supporting collection management,
partitioning, and efficient vector operations with various distance metrics.

Key Features:
    - Collection and partition management
    - Distance metrics (L2, Inner Product, Cosine)
    - Index types (IVF_FLAT, HNSW, etc.)
    - Expression-based filtering
    - Collection loading and release
    - Batch insert and search operations
    - Collection statistics and monitoring
    - Optional dependency handling

Main Classes:
    - MilvusStore: Main Milvus store for vector operations
    - MilvusClient: Milvus client wrapper
    - MilvusCollection: Collection wrapper with operations
    - MilvusSearch: Search operations and filtering

Example Usage:
    >>> from semantica.vector_store import MilvusStore
    >>> store = MilvusStore(host="localhost", port=19530)
    >>> store.connect()
    >>> collection = store.create_collection("my-collection", dimension=768, metric_type="L2")
    >>> store.insert_vectors(vectors)
    >>> collection.load()
    >>> results = store.search_vectors(query_vector, limit=10, expr="category == 'science'")
    >>> stats = store.get_stats()

Author: Semantica Contributors
License: MIT
"""

import math
import re
from typing import Any, Dict, List, Optional, Union

import numpy as np

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


def _validate_milvus_key(key: str) -> str:
    """Validate and escape a metadata filter key for Milvus queries."""
    if not key or not isinstance(key, str) or not re.match(r"^[a-zA-Z0-9_.-]+$", key):
        raise ValidationError(f"Invalid metadata filter key: '{key}'")
    return key.replace("\\", "\\\\").replace('"', '\\"')


def _format_milvus_value(val: Any) -> str:
    """Format and escape a filter value for Milvus expression syntax."""
    if isinstance(val, bool):
        return "true" if val else "false"
    elif isinstance(val, (int, float)):
        if isinstance(val, float) and not math.isfinite(val):
            raise ValidationError(
                f"Invalid metadata filter value: {val!r}. NaN/Infinity are not "
                "valid Milvus expression literals."
            )
        return str(val)
    elif isinstance(val, str):
        escaped = (
            val.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )
        return f'"{escaped}"'
    elif val is None:
        return "null"
    else:
        escaped = (
            str(val)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )
        return f'"{escaped}"'

# Optional Milvus import
try:
    from pymilvus import (
        Collection,
        CollectionSchema,
        DataType,
        FieldSchema,
        MilvusException,
        connections,
        utility,
    )

    MILVUS_AVAILABLE = True
except (ImportError, OSError):
    MILVUS_AVAILABLE = False
    connections = None
    Collection = None
    FieldSchema = None
    CollectionSchema = None
    DataType = None
    utility = None
    MilvusException = None


class MilvusClient:
    """Milvus client wrapper."""

    def __init__(self, alias: str = "default"):
        """Initialize Milvus client wrapper."""
        self.alias = alias
        self.logger = get_logger("milvus_client")

    def connect(
        self,
        host: str = "localhost",
        port: int = 19530,
        user: Optional[str] = None,
        password: Optional[str] = None,
        **options,
    ) -> bool:
        """Connect to Milvus server."""
        if not MILVUS_AVAILABLE:
            raise ProcessingError("Milvus not available")

        try:
            connections.connect(
                alias=self.alias,
                host=host,
                port=port,
                user=user,
                password=password,
                **options,
            )
            return True
        except Exception as e:
            raise ProcessingError(f"Failed to connect to Milvus: {str(e)}")

    def disconnect(self):
        """Disconnect from Milvus server."""
        if not MILVUS_AVAILABLE:
            return

        try:
            connections.disconnect(self.alias)
        except Exception as e:
            self.logger.warning(f"Failed to disconnect: {str(e)}")


class MilvusCollection:
    """Milvus collection wrapper."""

    def __init__(self, collection: Any, collection_name: str):
        """Initialize Milvus collection wrapper."""
        self.collection = collection
        self.collection_name = collection_name
        self.logger = get_logger("milvus_collection")

    def insert(self, data: List[List[Any]], **options) -> Any:
        """Insert data into collection."""
        if not MILVUS_AVAILABLE:
            raise ProcessingError("Milvus not available")

        try:
            insert_result = self.collection.insert(data, **options)
            return insert_result
        except Exception as e:
            raise ProcessingError(f"Failed to insert data: {str(e)}")

    def search(
        self,
        vectors: List[np.ndarray],
        anns_field: str,
        param: Dict[str, Any],
        limit: int = 10,
        expr: Optional[str] = None,
        **options,
    ) -> List[Dict[str, Any]]:
        """Search vectors in collection."""
        if not MILVUS_AVAILABLE:
            raise ProcessingError("Milvus not available")

        try:
            search_results = self.collection.search(
                data=[v.tolist() for v in vectors],
                anns_field=anns_field,
                param=param,
                limit=limit,
                expr=expr,
                **options,
            )

            results = []
            for hits in search_results:
                batch_results = []
                for hit in hits:
                    batch_results.append(
                        {
                            "id": hit.id,
                            "distance": hit.distance,
                            "score": 1.0 / (1.0 + max(0.0, hit.distance)),
                            # Milvus collection schema stores only id+vector; no
                            # metadata field is defined in create_collection().
                            # Return empty dict — a future schema migration that
                            # adds a metadata JSON field is tracked separately.
                            "metadata": {},
                            "vector": None,
                        }
                    )
                results.append(batch_results)

            return results[0] if len(results) == 1 else results
        except Exception as e:
            raise ProcessingError(f"Failed to search: {str(e)}")

    def load(self, **options) -> bool:
        """Load collection into memory."""
        if not MILVUS_AVAILABLE:
            raise ProcessingError("Milvus not available")

        try:
            self.collection.load(**options)
            return True
        except Exception as e:
            raise ProcessingError(f"Failed to load collection: {str(e)}")

    def release(self) -> bool:
        """Release collection from memory."""
        if not MILVUS_AVAILABLE:
            raise ProcessingError("Milvus not available")

        try:
            self.collection.release()
            return True
        except Exception as e:
            raise ProcessingError(f"Failed to release collection: {str(e)}")


class MilvusSearch:
    """Milvus search operations."""

    def __init__(self, collection: MilvusCollection):
        """Initialize Milvus search."""
        self.collection = collection
        self.logger = get_logger("milvus_search")

    def similarity_search(
        self,
        query_vector: np.ndarray,
        limit: int = 10,
        metric_type: str = "L2",
        expr: Optional[str] = None,
        **options,
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search.

        Args:
            query_vector: Query vector
            limit: Number of results
            metric_type: Distance metric ("L2", "IP", "COSINE")
            expr: Filter expression
            **options: Additional options

        Returns:
            List of search results
        """
        search_params = {
            "metric_type": metric_type,
            "params": options.get("params", {"nprobe": 10}),
        }

        return self.collection.search(
            vectors=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=limit,
            expr=expr,
            **options,
        )


# ---------------- Tri-representation primitives (Milvus 3.x) ----------------
# bge-m3 三路召回基元（PRD-0004/ADR 0013，检索基元下沉 fork 定案）：
# dense FLOAT_VECTOR + sparse SPARSE_FLOAT_VECTOR + ColBERT StructArray 多向量，
# 一次建齐 schema。读写均走 pymilvus MilvusClient（3.x 原生路径）；旧 ORM
# 单稠密路径（create_collection/add_vectors）保持不变、向后兼容。

TRI_DENSE_FIELD = "vector"
TRI_SPARSE_FIELD = "sparse"
TRI_STRUCT_FIELD = "tokens"
TRI_STRUCT_VECTOR_FIELD = "emb"
TRI_METADATA_FIELD = "metadata"


def build_tri_collection_schema(
    dimension: int, colbert_dim: int, colbert_max_capacity: int = 512
):
    """Assemble the tri-representation collection schema (Milvus 3.x StructArray).

    Fields: id VARCHAR(pk) / vector FLOAT_VECTOR(dim) / sparse SPARSE_FLOAT_VECTOR
    / metadata JSON / tokens ARRAY<STRUCT{emb FLOAT_VECTOR(colbert_dim)}>.
    Note: STRUCT fields land in schema._struct_fields and serialize under the
    separate "struct_fields" key of schema.to_dict() (verified offline against
    pymilvus 3.0.1 — schema.fields does not list them, which is expected).
    """
    if not MILVUS_AVAILABLE:
        raise ProcessingError("Milvus not available. Install it with: pip install pymilvus")
    from pymilvus import DataType
    from pymilvus import MilvusClient as _PyMilvusClient

    struct = _PyMilvusClient.create_struct_field_schema()
    struct.add_field(TRI_STRUCT_VECTOR_FIELD, DataType.FLOAT_VECTOR, dim=colbert_dim)

    schema = _PyMilvusClient.create_schema()
    schema.add_field(
        "id", DataType.VARCHAR, is_primary=True, auto_id=False, max_length=65535
    )
    schema.add_field(TRI_DENSE_FIELD, DataType.FLOAT_VECTOR, dim=dimension)
    schema.add_field(TRI_SPARSE_FIELD, DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field(TRI_METADATA_FIELD, DataType.JSON)
    schema.add_field(
        TRI_STRUCT_FIELD,
        DataType.ARRAY,
        element_type=DataType.STRUCT,
        struct_schema=struct,
        max_capacity=colbert_max_capacity,
    )
    return schema


def build_tri_index_params(dense_metric: str = "COSINE", colbert_metric: str = "MAX_SIM_COSINE"):
    """Index plan for the three vector fields (dense IVF_FLAT / sparse inverted / StructArray subfield)."""
    if not MILVUS_AVAILABLE:
        raise ProcessingError("Milvus not available. Install it with: pip install pymilvus")
    from pymilvus import MilvusClient as _PyMilvusClient

    index_params = _PyMilvusClient.prepare_index_params()
    index_params.add_index(
        field_name=TRI_DENSE_FIELD, index_type="IVF_FLAT",
        metric_type=dense_metric, params={"nlist": 1024},
    )
    index_params.add_index(
        field_name=TRI_SPARSE_FIELD, index_type="SPARSE_INVERTED_INDEX", metric_type="IP",
    )
    index_params.add_index(
        field_name=f"{TRI_STRUCT_FIELD}[{TRI_STRUCT_VECTOR_FIELD}]",
        index_type="AUTOINDEX", metric_type=colbert_metric,
    )
    return index_params


def create_tri_collection(
    client,
    collection_name: str,
    dimension: int,
    colbert_dim: Optional[int] = None,
    colbert_max_capacity: int = 512,
    dense_metric: str = "COSINE",
    colbert_metric: str = "MAX_SIM_COSINE",
):
    """Create a tri-representation collection via a pymilvus MilvusClient.

    Caller owns idempotency (drop first via drop_collection_if_exists for
    batch re-ingestion); raises if the collection already exists.
    """
    schema = build_tri_collection_schema(
        dimension, colbert_dim or dimension, colbert_max_capacity=colbert_max_capacity
    )
    index_params = build_tri_index_params(dense_metric=dense_metric, colbert_metric=colbert_metric)
    client.create_collection(
        collection_name=collection_name, schema=schema, index_params=index_params
    )
    return schema


def drop_collection_if_exists(client, collection_name: str) -> bool:
    """Drop a collection if present (idempotent re-ingestion cleanup). Returns whether dropped."""
    if client.has_collection(collection_name):
        client.drop_collection(collection_name)
        return True
    return False


def insert_tri_vectors(
    client,
    collection_name: str,
    dense,
    sparse,
    colbert,
    metadata: Optional[List[Dict[str, Any]]] = None,
    ids: Optional[List[str]] = None,
    max_batch_bytes: int = 16 * 1024 * 1024,
    max_batch_rows: int = 4096,
) -> List[str]:
    """Insert tri-representation rows (row-dict payload, MilvusClient.insert).

    dense: list of vectors; sparse: list of {token_id: weight} dicts;
    colbert: list of per-row token-vector arrays (np.ndarray or list[list[float]]).
    Per-row metadata/colbert entries are stored as empty placeholders —
    keeps the ColBERT backfill path open without a second re-ingest.

    Payloads are split into batches so a single gRPC message stays under the
    server's message-size ceiling: one full-document insert of 593 rows was
    measured at 888MB (ColBERT tokens dominate) and rejected with
    RESOURCE_EXHAUSTED (64MiB limit). Batches flush on max_batch_bytes
    (estimate) or max_batch_rows, whichever comes first.
    """
    import uuid as _uuid

    n = len(dense)
    if not (len(sparse) == len(colbert) == n):
        raise ValidationError(
            f"dense/sparse/colbert lengths must match (got {n}/{len(sparse)}/{len(colbert)})"
        )

    def _vec(v) -> List[float]:
        return v.tolist() if isinstance(v, np.ndarray) else [float(x) for x in v]

    def _estimate_bytes(row: dict) -> int:
        """Rough serialized-size estimate for a row (float32 for vector payloads)."""
        size = 8
        for key, val in row.items():
            if key == TRI_DENSE_FIELD:
                size += 4 * len(val)
            elif key == TRI_SPARSE_FIELD:
                size += 12 * len(val) + 16
            elif key == TRI_STRUCT_FIELD:
                size += 16 * len(val) + sum(4 * len(t[TRI_STRUCT_VECTOR_FIELD]) for t in val)
            else:
                size += len(str(val)) + 16
        return size

    rows = []
    for i in range(n):
        sp = sparse[i]
        cb = colbert[i]
        rows.append({
            "id": ids[i] if ids else str(_uuid.uuid4()),
            TRI_DENSE_FIELD: _vec(dense[i]),
            TRI_SPARSE_FIELD: dict(sp) if sp is not None else {},
            TRI_STRUCT_FIELD: (
                [{TRI_STRUCT_VECTOR_FIELD: _vec(t)} for t in cb] if cb is not None else []
            ),
            TRI_METADATA_FIELD: (metadata[i] if metadata and metadata[i] is not None else {}),
        })

    inserted_ids: List[str] = []
    batch: List[dict] = []
    batch_bytes = 0

    def _flush() -> None:
        nonlocal batch, batch_bytes
        if not batch:
            return
        client.insert(collection_name=collection_name, data=batch)
        inserted_ids.extend(row["id"] for row in batch)
        batch, batch_bytes = [], 0

    for row in rows:
        batch.append(row)
        batch_bytes += _estimate_bytes(row)
        if len(batch) >= max_batch_rows or batch_bytes >= max_batch_bytes:
            _flush()
    _flush()
    return inserted_ids


def search_tri_leg(
    client,
    collection_name: str,
    leg: str,
    query,
    top_k: int = 6,
    output_fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Single-leg search against a tri-representation collection.

    leg="dense":  query = dense vector (list/ndarray); COSINE, nprobe 16.
    leg="sparse": query = {token_id: weight} dict; IP.
    leg="colbert": query = token-vector array or a prebuilt pymilvus EmbeddingList;
                  anns_field "tokens[emb]", MAX_SIM_COSINE.

    Returns normalized hits: [{"id", "score", "metadata"}] (score = distance,
    higher = more similar for COSINE/IP/MAX_SIM alike).
    """
    if leg == "dense":
        vec = query.tolist() if isinstance(query, np.ndarray) else [float(x) for x in query]
        data, anns_field, params = [vec], TRI_DENSE_FIELD, {
            "metric_type": "COSINE", "params": {"nprobe": 16}}
    elif leg == "sparse":
        data, anns_field, params = [dict(query)], TRI_SPARSE_FIELD, {"metric_type": "IP"}
    elif leg == "colbert":
        data, anns_field, params = [_as_embedding_list(query)], (
            f"{TRI_STRUCT_FIELD}[{TRI_STRUCT_VECTOR_FIELD}]"), {
            "metric_type": "MAX_SIM_COSINE"}
    else:
        raise ValidationError(f"Unknown tri search leg: {leg!r} (dense|sparse|colbert)")

    results = client.search(
        collection_name=collection_name, data=data, anns_field=anns_field,
        search_params=params, limit=top_k,
        output_fields=output_fields or [TRI_METADATA_FIELD],
    )
    hits = results[0] if results else []
    out: List[Dict[str, Any]] = []
    for h in hits:
        entity = h.get("entity") or {}
        out.append({
            "id": h.get("id"),
            "score": float(h.get("distance", h.get("score", 0.0))),
            "metadata": entity.get(TRI_METADATA_FIELD) or {},
        })
    return out


def _as_embedding_list(query):
    """Wrap ColBERT token vectors into a pymilvus EmbeddingList query object."""
    from pymilvus.client.embedding_list import EmbeddingList

    if isinstance(query, EmbeddingList):
        return query
    el = EmbeddingList()
    el.add_batch(np.asarray(query, dtype=np.float32))
    return el


class MilvusStore:
    """
    Milvus store for vector storage and similarity search.

    • Milvus connection and authentication
    • Collection and partition management
    • Vector storage and retrieval
    • Similarity search and filtering
    • Performance optimization
    • Error handling and recovery
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        user: Optional[str] = None,
        password: Optional[str] = None,
        **config,
    ):
        """Initialize Milvus store."""
        self.logger = get_logger("milvus_store")
        self.config = config
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True
        self.host = host or config.get("host", "localhost")
        self.port = port or config.get("port", 19530)
        self.user = user or config.get("user")
        self.password = password or config.get("password")

        self.client: Optional[MilvusClient] = None
        self.collection: Optional[MilvusCollection] = None
        self.search_engine: Optional[MilvusSearch] = None
        self._tri_client = None  # pymilvus MilvusClient（三表征路径，懒建）

        # Check Milvus availability
        if not MILVUS_AVAILABLE:
            self.logger.warning(
                "Milvus not available. Install with: pip install pymilvus"
            )

    def connect(self, **options) -> bool:
        """
        Connect to Milvus service.

        Args:
            **options: Connection options

        Returns:
            True if connected successfully
        """
        if not MILVUS_AVAILABLE:
            raise ProcessingError(
                "Milvus is not available. Install it with: pip install pymilvus"
            )

        try:
            self.client = MilvusClient()
            self.client.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                **options,
            )

            self.logger.info(f"Connected to Milvus at {self.host}:{self.port}")
            return True
        except Exception as e:
            raise ProcessingError(f"Failed to connect to Milvus: {str(e)}")

    def create_collection(
        self, collection_name: str, dimension: int, metric_type: str = "L2", **options
    ) -> MilvusCollection:
        """
        Create Milvus collection.

        Args:
            collection_name: Name of the collection
            dimension: Vector dimension
            metric_type: Distance metric ("L2", "IP", "COSINE")
            **options: Additional options

        Returns:
            MilvusCollection instance
        """
        if self.client is None:
            self.connect()

        if not MILVUS_AVAILABLE:
            raise ProcessingError("Milvus not available")

        try:
            # Check if collection exists
            if utility.has_collection(collection_name):
                self.logger.info(f"Collection {collection_name} already exists")
                return self.get_collection(collection_name)

            # Define schema
            fields = [
                FieldSchema(
                    name="id", dtype=DataType.VARCHAR, is_primary=True, auto_id=False, max_length=65535
                ),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
                FieldSchema(name="metadata", dtype=DataType.JSON),
            ]

            schema = CollectionSchema(
                fields=fields, description=f"Vector collection for {collection_name}"
            )

            # Create collection
            collection = Collection(name=collection_name, schema=schema)

            # Create index
            index_params = {
                "metric_type": metric_type,
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024},
            }
            collection.create_index(field_name="vector", index_params=index_params)

            self.collection = MilvusCollection(collection, collection_name)
            self.search_engine = MilvusSearch(self.collection)

            self.logger.info(f"Created Milvus collection: {collection_name}")
            return self.collection

        except Exception as e:
            raise ProcessingError(f"Failed to create collection: {str(e)}")

    def get_collection(self, collection_name: str) -> MilvusCollection:
        """
        Get existing collection.

        Args:
            collection_name: Name of the collection

        Returns:
            MilvusCollection instance
        """
        if self.client is None:
            self.connect()

        if not MILVUS_AVAILABLE:
            raise ProcessingError("Milvus not available")

        try:
            if not utility.has_collection(collection_name):
                raise ProcessingError(f"Collection {collection_name} does not exist")

            collection = Collection(collection_name)
            # Reject schemas that don't match create_collection()'s shape:
            # id/VARCHAR pk + vector + metadata. Otherwise an incompatible
            # collection attaches and fails far later in get_vector/get_metadata.
            schema = getattr(collection, "schema", None)
            fields = list(getattr(schema, "fields", None) or [])
            pk = [f for f in fields if getattr(f, "is_primary", False)]
            if (
                not pk
                or pk[0].name != "id"
                or getattr(getattr(pk[0], "dtype", None), "name", None) != "VARCHAR"
                or getattr(pk[0], "auto_id", False)
            ):
                raise ProcessingError(
                    f"Collection '{collection_name}' has an invalid primary key: "
                    "expected VARCHAR field 'id' without auto_id"
                )
            vector_field = next((f for f in fields if f.name == "vector"), None)
            if vector_field is None:
                raise ProcessingError(
                    f"Collection '{collection_name}' is missing required field 'vector'"
                )
            if (
                getattr(getattr(vector_field, "dtype", None), "name", None)
                != "FLOAT_VECTOR"
            ):
                raise ProcessingError(
                    f"Collection '{collection_name}' has an invalid vector field: "
                    "expected FLOAT_VECTOR 'vector'"
                )
            metadata_field = next((f for f in fields if f.name == "metadata"), None)
            if metadata_field is None:
                raise ProcessingError(
                    f"Collection '{collection_name}' is missing required field 'metadata'"
                )
            if getattr(getattr(metadata_field, "dtype", None), "name", None) != "JSON":
                raise ProcessingError(
                    f"Collection '{collection_name}' has an invalid metadata field: "
                    "expected JSON 'metadata'"
                )

            self.collection = MilvusCollection(collection, collection_name)
            self.search_engine = MilvusSearch(self.collection)
            return self.collection
        except Exception as e:
            raise ProcessingError(f"Failed to get collection: {str(e)}")

    def insert_vectors(self, vectors: List[Union[np.ndarray, List[float]]], **options) -> Any:
        """Backward compatibility alias for add_vectors."""
        return self.add_vectors(vectors, **options)

    def add_vectors(
        self, 
        vectors: List[Union[np.ndarray, List[float]]], 
        ids: Optional[List[str]] = None,
        metadata: Optional[List[Dict[str, Any]]] = None,
        **options
    ) -> List[str]:
        """
        Add vectors to collection.

        Args:
            vectors: List of vectors
            ids: Optional list of vector IDs
            metadata: Optional list of metadata dictionaries
            **options: Additional options

        Returns:
            List of vector IDs
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="vector_store",
            submodule="MilvusStore",
            message=f"Inserting {len(vectors)} vectors into Milvus collection",
        )

        try:
            if self.collection is None:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message="Collection not initialized"
                )
                raise ProcessingError(
                    "Collection not initialized. Call create_collection() or get_collection() first."
                )

            if not MILVUS_AVAILABLE:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message="Milvus not available"
                )
                raise ProcessingError("Milvus not available")

            # Convert vectors to list format
            self.progress_tracker.update_tracking(
                tracking_id, message="Converting vectors to list format..."
            )
            vector_data = []
            for vector in vectors:
                if isinstance(vector, np.ndarray):
                    vector = vector.tolist()
                vector_data.append(vector)

            import uuid
            if ids is None:
                ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
                
            if metadata is None:
                metadata = [{} for _ in range(len(vectors))]

            data = [ids, vector_data, metadata]
            
            self.progress_tracker.update_tracking(
                tracking_id, message="Inserting vectors into collection..."
            )
            result = self.collection.insert(data, **options)

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Inserted {len(vectors)} vectors",
            )
            return ids

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise ProcessingError(f"Failed to insert vectors: {str(e)}")

    def search_vectors(
        self,
        query_vector: np.ndarray,
        limit: int = 10,
        metric_type: str = "L2",
        expr: Optional[str] = None,
        **options,
    ) -> List[Dict[str, Any]]:
        """
        Search vectors in collection.

        Args:
            query_vector: Query vector
            limit: Number of results
            metric_type: Distance metric
            expr: Filter expression
            **options: Additional options

        Returns:
            List of search results
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="vector_store",
            submodule="MilvusStore",
            message=f"Searching for {limit} similar vectors in Milvus",
        )

        try:
            if self.search_engine is None:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message="Collection not initialized"
                )
                raise ProcessingError(
                    "Collection not initialized. Call create_collection() or get_collection() first."
                )

            # Load collection if not loaded
            if not self.collection.collection.has_index():
                self.progress_tracker.update_tracking(
                    tracking_id, message="Loading collection..."
                )
                self.collection.load()

            self.progress_tracker.update_tracking(
                tracking_id, message="Performing similarity search..."
            )
            results = self.search_engine.similarity_search(
                query_vector, limit, metric_type, expr, **options
            )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Found {len(results)} similar vectors",
            )
            return results
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def delete_vectors(self, vector_ids: List[str], **options) -> Dict[str, Any]:
        """Delete vectors from collection by their ids.

        Args:
            vector_ids: Vector ids to delete
            **options: Additional options

        Returns:
            A dict with the number of matching entities that were deleted
            (``delete_count``).
        """
        if self.collection is None:
            raise ProcessingError(
                "Collection not initialized. Call create_collection() or get_collection() first."
            )

        if not vector_ids:
            return {"delete_count": 0}

        try:
            # Milvus DELETE deletes by expression. Escape each id so a quote or
            # backslash in an id cannot break out of the string literal.
            if len(vector_ids) == 1:
                expr = f"id == {_format_milvus_value(vector_ids[0])}"
            else:
                formatted = ", ".join(_format_milvus_value(i) for i in vector_ids)
                expr = f"id in [{formatted}]"
            result = self.collection.collection.delete(expr=expr, **options)
            delete_count = getattr(result, "delete_count", 0)
            if delete_count is None:
                delete_count = 0
            elif isinstance(delete_count, (str, bytes)):
                try:
                    delete_count = int(delete_count)
                except (TypeError, ValueError):
                    delete_count = 0
            return {"delete_count": delete_count}
        except Exception as e:
            raise ProcessingError(f"Failed to delete vectors: {str(e)}")

    def get_vector(self, vector_id: str) -> Optional[np.ndarray]:
        """Get vector by ID."""
        if not MILVUS_AVAILABLE or not self.collection:
            return None

        try:
            safe_id = vector_id.replace("\\", "\\\\").replace('"', '\\"')
            res = self.collection.collection.query(
                expr=f'id == "{safe_id}"',
                output_fields=["vector"]
            )
            if res and len(res) > 0:
                return np.array(res[0]["vector"])
            return None
        except Exception:
            return None

    def get_metadata(self, vector_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata by ID."""
        if not MILVUS_AVAILABLE or not self.collection:
            return None

        try:
            safe_id = vector_id.replace("\\", "\\\\").replace('"', '\\"')
            res = self.collection.collection.query(
                expr=f'id == "{safe_id}"',
                output_fields=["metadata"]
            )
            if res and len(res) > 0:
                return res[0].get("metadata", {})
            return None
        except Exception:
            return None

    @staticmethod
    def _record_to_result(item: Dict[str, Any]) -> Dict[str, Any]:
        vec = item.get("vector")
        return {
            "id": str(item.get("id")),
            "metadata": item.get("metadata") or {},
            "vector": np.array(vec) if vec is not None else None,
        }

    def filter_by_metadata(
        self, filters: Dict[str, Any], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Filter vectors by metadata using Milvus expression filtering.

        Args:
            filters: Metadata filter criteria
            limit: Maximum number of results

        Returns:
            List of matching result dicts with 'id', 'metadata', and 'vector'
        """
        if self.collection is None or not MILVUS_AVAILABLE:
            return []

        expr_parts = []
        if filters:
            for key, value in filters.items():
                safe_key = _validate_milvus_key(key)
                if isinstance(value, dict):
                    if "min" in value and value["min"] is not None:
                        min_val = _format_milvus_value(value["min"])
                        expr_parts.append(f'metadata["{safe_key}"] >= {min_val}')
                    if "max" in value and value["max"] is not None:
                        max_val = _format_milvus_value(value["max"])
                        expr_parts.append(f'metadata["{safe_key}"] <= {max_val}')
                elif isinstance(value, list):
                    formatted_vals = [_format_milvus_value(v) for v in value]
                    expr_parts.append(
                        f'metadata["{safe_key}"] in [{", ".join(formatted_vals)}]'
                    )
                else:
                    formatted_val = _format_milvus_value(value)
                    expr_parts.append(f'metadata["{safe_key}"] == {formatted_val}')

        expr = " and ".join(expr_parts) if expr_parts else "id != ''"

        try:
            query_results = self.collection.collection.query(
                expr=expr,
                limit=limit,
                output_fields=["id", "vector", "metadata"],
            )
            return [self._record_to_result(item) for item in query_results]
        except Exception as e:
            self.logger.warning(f"Failed to query Milvus vectors by metadata expression: {e}")
            return []

    def iter_all(self, batch_size: int = 500):
        """
        Iterate over every stored entity using Milvus's query iterator.

        Paginates by primary-key cursor rather than row offset, which is why
        this exists instead of scan_vectors(offset, limit). query(offset=...)
        is capped by the 16384 result window and would truncate anything
        larger.

        Assumes the schema create_collection() builds: a VARCHAR `id` primary
        key plus vector and metadata fields, as get_vector() and
        filter_by_metadata() already do. get_collection() does not validate
        schema, so a collection with an integer key or no metadata field fails
        here.

        Args:
            batch_size: Entities to request per iterator batch

        Yields:
            Result dicts with 'id', 'metadata', and 'vector', in cursor order

        Raises:
            ProcessingError: If the collection is not initialized, or the
                installed pymilvus does not expose query_iterator().
        """
        if self.collection is None:
            raise ProcessingError(
                "Collection not initialized. Call create_collection() or get_collection() first."
            )

        if not MILVUS_AVAILABLE:
            raise ProcessingError("Milvus not available")

        query_iterator = getattr(self.collection.collection, "query_iterator", None)
        if not callable(query_iterator):
            raise ProcessingError(
                "This pymilvus version does not expose Collection.query_iterator(), "
                "which full enumeration requires. Falling back to query(offset=...) "
                "is not safe here: it is capped by the 16384 result window and would "
                "silently truncate a larger collection."
            )

        # Query operations need a loaded collection. Idempotent, and once per
        # scan rather than per batch.
        self.collection.load()

        # Milvus rejects an empty expression; this match-all form is what
        # filter_by_metadata() already uses.
        iterator = query_iterator(
            batch_size=batch_size,
            expr="id != ''",
            output_fields=["id", "vector", "metadata"],
        )

        try:
            while True:
                batch = iterator.next()
                if not batch:
                    return
                for item in batch:
                    yield self._record_to_result(item)
        finally:
            # Release the server-side iterator even if the consumer stops early.
            # Swallowed so a broken connection at cleanup time doesn't replace
            # whatever real exception was already propagating out of the try.
            close = getattr(iterator, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as e:
                    self.logger.warning(f"Failed to close Milvus query iterator: {e}")

    def get_stats(self, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """Get collection statistics."""
        if self.collection is None and collection_name:
            self.get_collection(collection_name)

        if self.collection is None:
            raise ProcessingError(
                "Collection not initialized. Call create_collection() or get_collection() first."
            )

        try:
            stats = self.collection.collection.num_entities
            return {
                "entity_count": stats,
                "collection_name": self.collection.collection_name,
            }
        except Exception as e:
            self.logger.warning(f"Failed to get stats: {str(e)}")
            return {"status": "unknown"}

    # ---------------- Tri-representation API (Milvus 3.x MilvusClient path) ----------------

    def _pymilvus_client(self):
        """Lazily build a pymilvus MilvusClient from this store's host/port.

        Coexists with the ORM alias connection (legacy single-dense path);
        the tri path uses the 3.x-native MilvusClient API (StructArray schema,
        row-dict insert, per-leg search).
        """
        if getattr(self, "_tri_client", None) is None:
            from pymilvus import MilvusClient as _PyMilvusClient

            self._tri_client = _PyMilvusClient(uri=f"http://{self.host}:{self.port}")
        return self._tri_client

    def create_tri_collection(
        self, collection_name: str, dimension: int, colbert_dim: Optional[int] = None,
        colbert_max_capacity: int = 512, **options,
    ):
        """Create a tri-representation collection (dense+sparse+ColBERT fields in one schema).

        Backward-compatible addition: the legacy create_collection() single-dense
        path is untouched. Idempotent re-ingestion callers should drop first via
        drop_collection().
        """
        return create_tri_collection(
            self._pymilvus_client(), collection_name, dimension,
            colbert_dim=colbert_dim or dimension,
            colbert_max_capacity=colbert_max_capacity, **options,
        )

    def drop_collection(self, collection_name: str) -> bool:
        """Drop a collection if present (idempotent). MilvusClient path."""
        return drop_collection_if_exists(self._pymilvus_client(), collection_name)

    def insert_tri_vectors(self, dense, sparse, colbert, collection_name: str = "",
                           metadata=None, ids=None, **options) -> List[str]:
        """Insert tri-representation rows into the collection created via create_tri_collection."""
        del options  # 与旧签名家族一致接收 kwargs（暂未使用）
        name = collection_name or (self.collection.collection_name if self.collection else "")
        if not name:
            raise ProcessingError("Collection not initialized or collection_name missing")
        return insert_tri_vectors(
            self._pymilvus_client(), name, dense, sparse, colbert,
            metadata=metadata, ids=ids,
        )

    def search_tri_leg(self, collection_name: str, leg: str, query, top_k: int = 6,
                       **options) -> List[Dict[str, Any]]:
        """Single-leg search (dense|sparse|colbert) against a tri collection."""
        return search_tri_leg(
            self._pymilvus_client(), collection_name, leg, query, top_k=top_k, **options
        )

    def load_tri_collection(self, collection_name: str) -> None:
        """Load a tri collection into memory (search readiness; MilvusClient path)."""
        self._pymilvus_client().load_collection(collection_name)
