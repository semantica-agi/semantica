---
title: "Vector Store Module"
description: "Unified interface for FAISS, Pinecone, Weaviate, Qdrant, Milvus, and PgVector with hybrid search."
icon: "database"
---

`semantica.vector_store` provides a unified API for storing and searching vector embeddings across all major backends. Swap backends with a one-line change — no application code changes needed.

## What You Get

- **`VectorStore`** — unified interface across all backends
- **Backends** — FAISS, Pinecone, Weaviate, Qdrant, Milvus, PgVector, in-memory
- **Hybrid search** — combine dense vector similarity with sparse keyword/metadata filtering
- **Metadata filtering** — rich filter expressions: `eq`, `ne`, `gt`, `lt`, `in`, `contains`, `$and`, `$or`
- **Namespace isolation** — multi-tenant support via isolated namespaces
- **Batch operations** — bulk add, delete, and metadata updates

## Basic Usage

```python
from semantica.vector_store import VectorStore

# In-memory (development)
store = VectorStore(backend="inmemory", dimension=768)

# FAISS (local, production)
store = VectorStore(backend="faiss", dimension=768, index_path="store.faiss")

# Add vectors
store.add_vectors(embeddings=embeddings, ids=["doc1", "doc2"], metadata=[{}, {}])

# Semantic search
results = store.search(query_vector, top_k=10)
for r in results:
    print(f"{r['id']} — score: {r['score']:.3f}")
    print(f"  metadata: {r['metadata']}")
```

## Backends

<Tabs>
  <Tab title="FAISS">

```python
store = VectorStore(
    backend="faiss",
    dimension=768,
    index_type="IVF",       # "Flat" | "IVF" | "HNSW"
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

Combine vector similarity with keyword/metadata filters for higher precision:

```python
results = store.hybrid_search(
    query_vector=query_embedding,
    query_text="machine learning",  # keyword component
    top_k=10,
    alpha=0.7,                      # 0.0 = keyword only, 1.0 = vector only
    filters={"category": "research", "year": {"$gte": 2022}}
)
```

## Metadata Filtering

```python
# Equality
results = store.search(query_vector, filters={"author": "John Smith"})

# Range
results = store.search(query_vector, filters={"date": {"$gte": "2023-01-01"}})

# Set membership
results = store.search(query_vector, filters={"tag": {"$in": ["ai", "ml"]}})

# Compound AND
results = store.search(query_vector, filters={
    "$and": [
        {"category": "research"},
        {"year": {"$gte": 2022}}
    ]
})
```

## Namespace Isolation

Isolate vectors per tenant, project, or use case:

```python
store = VectorStore(backend="faiss", dimension=768)

# Write to separate namespaces
store.add_vectors(embeddings_a, ids_a, namespace="tenant_a")
store.add_vectors(embeddings_b, ids_b, namespace="tenant_b")

# Search is scoped to the specified namespace
results = store.search(query_vector, namespace="tenant_a")
```

## Batch Operations

```python
# Batch add — automatically chunked for memory efficiency
store.add_vectors_batch(embeddings_list, ids_list, batch_size=1000)

# Batch delete
store.delete_vectors(ids=["doc1", "doc2", "doc3"])

# Update metadata without re-embedding
store.update_metadata("doc1", {"status": "archived", "reviewed": True})
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
