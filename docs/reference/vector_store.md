---
title: "Vector Store Module"
description: "Unified interface for FAISS, Pinecone, Weaviate, Qdrant, Milvus, and PgVector with hybrid search."
icon: "database"
---

`semantica.vector_store` provides a unified API for storing and searching vector embeddings across all major backends. Swap backends with a one-line change — no application code changes needed.

## What You Get

<CardGroup cols={2}>
  <Card title="VectorStore" icon="database">
    Unified interface across FAISS, Pinecone, Weaviate, Qdrant, Milvus, and PgVector.
  </Card>
  <Card title="HybridSearch" icon="magnifying-glass">
    Combine dense vector similarity with sparse keyword/BM25 filtering and configurable fusion strategies.
  </Card>
  <Card title="MetadataStore" icon="table">
    Rich metadata indexing and schema management — query by field values without a vector.
  </Card>
  <Card title="NamespaceManager" icon="folder-tree">
    Multi-tenant namespace isolation — structural separation, not just metadata filters.
  </Card>
  <Card title="Batch Operations" icon="layer-group">
    Bulk add, delete, and metadata updates — automatically chunked for memory efficiency.
  </Card>
  <Card title="FAISS Index Types" icon="chart-scatter">
    Flat, IVF, HNSW, and PQ index types with full configuration control.
  </Card>
</CardGroup>

## Quick Start

<Steps>
  <Step title="Create a vector store">
    ```python
    from semantica.vector_store import VectorStore

    # In-memory (development)
    store = VectorStore(backend="inmemory", dimension=768)

    # FAISS (local production — persists to disk)
    store = VectorStore(backend="faiss", dimension=768, index_path="store.faiss")
    ```
  </Step>
  <Step title="Add vectors">
    ```python
    # Add text documents (auto-embedded)
    ids = store.add_documents(
        documents=["text one", "text two"],
        metadata=[{"title": "Document 1"}, {"title": "Document 2"}]
    )

    # Add pre-computed vectors
    ids = store.store_vectors(
        vectors=[embedding1, embedding2],
        metadata=[{"title": "Document 1"}, {"title": "Document 2"}]
    )
    ```
  </Step>
  <Step title="Search by semantic similarity">
    ```python
    # Search by text query (auto-embeds the query)
    results = store.search("machine learning", limit=10)

    # Search by pre-computed vector
    results = store.search_vectors(query_vector, k=10)

    for r in results:
        print(f"{r['id']} — score: {r['score']:.3f}")
    ```
  </Step>
  <Step title="Filter results by metadata">
    ```python
    from semantica.vector_store import HybridSearch, MetadataFilter

    mf = MetadataFilter().eq("category", "research").gt("year", 2022)

    search  = HybridSearch(vector_store=store)
    results = search.search(query=query_vector, k=10, metadata_filter=mf)
    ```
  </Step>
</Steps>

## Backends

<Tabs>
  <Tab title="FAISS">

```python
store = VectorStore(
    backend="faiss",
    dimension=768,
    index_type="IVF",       # "Flat" | "IVF" | "HNSW" | "PQ"
    index_path="store.faiss"
)
```

Best for: local development, on-premise production with no external services. No API key required.

  </Tab>
  <Tab title="Pinecone">

```bash
pip install "semantica[pinecone]"
```

```python
store = VectorStore(
    backend="pinecone",
    dimension=768,
    api_key=os.getenv("PINECONE_API_KEY"),
    index_name="semantica-index",
    environment="us-east-1-aws"
)
```

  </Tab>
  <Tab title="Weaviate">

```bash
pip install "semantica[weaviate]"
```

```python
store = VectorStore(
    backend="weaviate",
    dimension=768,
    url="http://localhost:8080",
    class_name="Document"
)
```

  </Tab>
  <Tab title="Qdrant">

```bash
pip install "semantica[qdrant]"
```

```python
store = VectorStore(
    backend="qdrant",
    dimension=768,
    url="http://localhost:6333",
    collection_name="semantica"
)
```

  </Tab>
  <Tab title="PgVector">

```bash
pip install "semantica[pgvector]"
```

```python
store = VectorStore(
    backend="pgvector",
    dimension=768,
    connection_string="postgresql://user:pass@localhost/db",
    table_name="embeddings"
)
```

See the [PgVector Guide](../vector_stores/pgvector) for full setup.

  </Tab>
</Tabs>

## Hybrid Search

Use `HybridSearch` with a `MetadataFilter` to combine vector similarity with metadata conditions:

```python
from semantica.vector_store import HybridSearch, MetadataFilter

mf = (
    MetadataFilter()
    .eq("category", "research")
    .gt("year", 2022)
)

search  = HybridSearch(vector_store=store)
results = search.search(
    query=query_vector,      # np.ndarray or query string (auto-embedded)
    k=10,
    metadata_filter=mf
)

for r in results:
    print(f"{r['id']} — score: {r['score']:.3f}  metadata: {r['metadata']}")
```

## Metadata Filtering

`MetadataFilter` supports chained conditions — all conditions are ANDed:

```python
from semantica.vector_store import MetadataFilter

mf = MetadataFilter().eq("author", "John Smith")          # equality
mf = MetadataFilter().ne("status", "archived")            # not equal
mf = MetadataFilter().gt("year", 2022).lte("year", 2024)  # range
mf = MetadataFilter().in_list("tag", ["ai", "ml"])        # set membership
mf = MetadataFilter().contains("title", "neural")         # substring / list contains

# Multiple conditions — all must match (AND)
mf = (
    MetadataFilter()
    .eq("category", "research")
    .gt("year", 2022)
    .contains("title", "language model")
)
```

## Namespace Isolation

Use `NamespaceManager` to assign vectors to named namespaces for multi-tenant isolation:

```python
from semantica.vector_store import NamespaceManager, VectorStore

store      = VectorStore(backend="faiss", dimension=768)
ns_manager = NamespaceManager()

ns_manager.create_namespace("tenant_a", description="Customer A data")
ns_manager.create_namespace("tenant_b", description="Customer B data")

# Store vectors, then assign them to a namespace
ids_a = store.store_vectors(embeddings_a, metadata=metadata_a)
for vid in ids_a:
    ns_manager.add_vector_to_namespace(vid, "tenant_a")

# List all namespace names
for name in ns_manager.list_namespaces():
    print(name)

ns_manager.delete_namespace("tenant_a")
```

## Batch Operations

```python
# Batch add text documents — chunked automatically by batch_size
ids = store.add_documents(
    documents=large_doc_list,
    metadata=large_meta_list,
    batch_size=1000
)

# Batch add pre-computed vectors
ids = store.store_vectors(vectors=embeddings_list, metadata=meta_list)

# Delete by vector ID list
store.delete_vectors(vector_ids=["vec_0", "vec_1", "vec_2"])

# Replace vectors (re-embed then update)
store.update_vectors(
    vector_ids=["vec_0"],
    new_vectors=[new_embedding]
)
```

## Backend Comparison

| Backend | Deployment | API Key | Hybrid Search | Best For |
| ------- | ---------- | ------- | ------------- | -------- |
| FAISS | Local | No | No | On-premise, offline |
| Pinecone | Cloud | Yes | Yes | Managed cloud, serverless |
| Weaviate | Self-hosted / Cloud | Optional | Yes | Rich metadata filtering |
| Qdrant | Self-hosted / Cloud | Optional | Yes | High-performance filtering |
| Milvus | Self-hosted | No | Yes | Large-scale production |
| PgVector | PostgreSQL | No | Limited | Postgres-native integration |
| In-memory | Process | No | No | Development, testing |

## HybridSearch

`HybridSearch` combines vector similarity with metadata filtering, and can fuse results from multiple sources:

```python
from semantica.vector_store import HybridSearch, MetadataFilter, SearchRanker

# Single-source search with metadata filter
search = HybridSearch(vector_store=store)
mf     = MetadataFilter().eq("category", "research").gt("year", 2022)

results = search.search(
    query=query_vector,   # np.ndarray or query string
    k=10,
    metadata_filter=mf
)

# Multi-source fusion (RRF across multiple stores)
sources = [
    {"vectors": v1, "metadata": m1, "ids": ids1},
    {"vectors": v2, "metadata": m2, "ids": ids2},
]
fused = search.multi_source_search(query_vector, sources, k=10)

# Custom fusion strategy
ranker = SearchRanker(strategy="reciprocal_rank_fusion")  # or "weighted_average"
fused  = ranker.rank([results_list_1, results_list_2], k=60)
```

| Fusion strategy | Description |
| --------------- | ----------- |
| `reciprocal_rank_fusion` | Rank-based combination via RRF constant `k=60` — robust to score scale differences |
| `weighted_average` | Weighted average of scores — pass `weights=[0.7, 0.3]` to `rank()` |

## MetadataStore

`MetadataStore` indexes structured metadata and lets you query by field values without a vector:

```python
from semantica.vector_store import MetadataStore

meta_store = MetadataStore()

# Define schema fields
meta_store.add_field("author",   str,   required=True)
meta_store.add_field("year",     int,   required=True)
meta_store.add_field("category", str)
meta_store.add_field("score",    float, default=0.0)

# Store and retrieve metadata
meta_store.store_metadata("doc1", {"author": "Alice", "year": 2024, "category": "research"})
meta_store.store_metadata("doc2", {"author": "Bob",   "year": 2023, "category": "review"})

# Query — returns List[str] of matching vector IDs
ids  = meta_store.query_metadata({"category": "research", "year": 2024})

# Get and update metadata for a specific vector
meta = meta_store.get_metadata("doc1")
meta_store.update_metadata("doc1", {"score": 0.92})
```

## NamespaceManager

Assigns vector IDs to named namespaces for multi-tenant or multi-model isolation:

```python
from semantica.vector_store import NamespaceManager

ns_manager = NamespaceManager()

ns_manager.create_namespace("tenant_a", description="Customer A data")
ns_manager.create_namespace("tenant_b", description="Customer B data")

# Assign vector IDs to a namespace after storing them
for vid in ids_a:
    ns_manager.add_vector_to_namespace(vid, "tenant_a")

# Inspect namespaces
for name in ns_manager.list_namespaces():   # returns List[str]
    print(name)

# Look up which namespace a vector belongs to
ns = ns_manager.get_vector_namespace("vec_0")

ns_manager.delete_namespace("tenant_a")
```

## FAISS Index Type Reference

| Index | Memory | Speed | Accuracy | When to Use |
| ----- | ------ | ----- | -------- | ----------- |
| `Flat` | High | Slow | Exact (100%) | < 100K vectors, correctness critical |
| `IVF` | Medium | Fast | ~95–98% | 100K–10M vectors, good balance |
| `HNSW` | Medium-High | Very fast | ~97–99% | Low latency, production retrieval |
| `PQ` | Low | Fast | ~90–95% | Millions of vectors, memory-constrained |

```python
# Flat — brute-force exact search
store = VectorStore(backend="faiss", dimension=768, index_type="Flat")

# IVF — inverted file index with nlist clusters
store = VectorStore(backend="faiss", dimension=768, index_type="IVF", nlist=100)

# HNSW — hierarchical navigable small world graph
store = VectorStore(backend="faiss", dimension=768, index_type="HNSW", M=16, ef_construction=200)

# PQ — product quantization for memory efficiency
store = VectorStore(backend="faiss", dimension=768, index_type="PQ", m=8)
```

## Similarity Metrics

| Metric | Constructor arg | Distance → Similarity | Best For |
| ------ | --------------- | --------------------- | -------- |
| Cosine | `metric="cosine"` | `1 - cosine_distance` | Text, embeddings |
| L2 (Euclidean) | `metric="l2"` | `1 / (1 + distance)` | Image features |
| Inner Product | `metric="ip"` | raw dot product | Recommendation systems |

```python
store = VectorStore(backend="faiss", dimension=768, metric="cosine")
```

## Tips and Common Pitfalls

<Warning>
  **Match vector dimension to your embedding model.** The `dimension` parameter must exactly match your embedding model's output size — `all-MiniLM-L6-v2` = 384, `all-mpnet-base-v2` = 768, `bge-large-en-v1.5` = 1024. A mismatch raises an error at insert time, not at store creation.
</Warning>

<Tip>
  **Use `Flat` index only for small datasets.** Flat (brute-force) search has perfect recall but O(n) query time. At 500K+ vectors, switch to `IVF` or `HNSW` — they sacrifice less than 5% recall for 100–1000x speedup.
</Tip>

<Warning>
  **Don't search without normalizing first.** If you disabled `normalize=True` in `EmbeddingGenerator`, compute cosine similarity with `metric="cosine"` (which normalizes internally). Raw dot product on un-normalized vectors produces incorrect similarity rankings.
</Warning>

<Tip>
  **Use `hybrid_search` for precision-sensitive workloads.** Pure vector search finds semantically similar results but may miss keyword matches important to the user. Hybrid search (vector + BM25) combines both signals — especially valuable for domain-specific terminology.
</Tip>

<Tip>
  **Use `NamespaceManager` for multi-tenant applications.** Storing all tenants' vectors in the same collection and filtering by metadata at query time is slow and leaks data if a filter is accidentally omitted. Namespace isolation is both faster (smaller search space) and safer (structural isolation).
</Tip>

<Warning>
  **Persist FAISS indexes to disk.** `VectorStore(backend="faiss", index_path="store.faiss")` saves the index to disk on each write. Without a path, the index is in-memory only and is lost on process exit.
</Warning>

<Tip>
  **Update metadata without re-embedding.** `store.update_metadata(id, {...})` changes attached fields (status, tags, review date) without re-running the embedding model. Use this for state changes that don't affect semantic content.
</Tip>

<CardGroup cols={2}>
  <Card title="Embeddings" icon="vector-square" href="embeddings">
    Generate the vectors stored here.
  </Card>
  <Card title="Context" icon="brain" href="context">
    AgentContext uses VectorStore for memory retrieval.
  </Card>
  <Card title="PgVector Guide" icon="database" href="../vector_stores/pgvector">
    PostgreSQL vector storage with pgvector extension.
  </Card>
  <Card title="Ingest" icon="download" href="ingest">
    Ingest documents before embedding and storing.
  </Card>
</CardGroup>
