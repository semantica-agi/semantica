# Vector Store Module Usage Guide

This comprehensive guide demonstrates how to use the vector store module for vector storage and retrieval, supporting multiple vector store backends (FAISS, Weaviate, Qdrant, Pinecone, Milvus), hybrid search combining vector similarity and metadata filtering, metadata management, namespace isolation, and enhanced decision tracking capabilities.

## Quick Imports

```python
# Core vector store classes
from semantica.vector_store import VectorStore, HybridSearch, MetadataFilter

# Decision tracking classes
from semantica.vector_store import DecisionEmbeddingPipeline, HybridSimilarityCalculator, DecisionContext

# Convenience functions
from semantica.vector_store.decision_vector_methods import (
    quick_decision, find_precedents, explain, similar_to,
    batch_decisions, filter_decisions, search_by_entities,
    set_global_vector_store
)

# Store adapters
from semantica.vector_store import FAISSStore, WeaviateStore, QdrantStore, PineconeStore, MilvusStore

# Utility classes
from semantica.vector_store import VectorManager, NamespaceManager, MetadataStore
```

## Quick Example

```python
# Simple vector store setup
vector_store = VectorStore(backend="inmemory", dimension=384)

# Store vectors
vectors = [[0.1, 0.2, 0.3, 0.4] for _ in range(10)]
metadata = [{"category": "document", "source": "test"} for _ in range(10)]
vector_ids = vector_store.store_vectors(vectors, metadata)

# Search vectors
query_vector = [0.1, 0.2, 0.3, 0.4]
results = vector_store.search_vectors(query_vector, k=5)
print(f"Found {len(results)} similar vectors")
```

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Vector Storage Operations](#vector-storage-operations)
3. [Similarity Search](#similarity-search)
4. [Index Management](#index-management)
5. [Hybrid Search](#hybrid-search)
6. [Metadata Management](#metadata-management)
7. [Namespace Management](#namespace-management)
8. [Store Backends](#store-adapters)
9. [Algorithms and Methods](#algorithms-and-methods)
10. [Configuration](#configuration)
11. [Complete Examples](#complete-examples)
12. [Decision Tracking](#decision-tracking)
13. [Hybrid Similarity for Decisions](#hybrid-similarity-for-decisions)
14. [Convenience Functions](#convenience-functions)

## Basic Usage

### Using VectorStore

```python
from semantica.vector_store import VectorStore
import numpy as np

# Create vector store
store = VectorStore(backend="faiss", dimension=768)

# Store vectors
vectors = [np.random.rand(768) for _ in range(100)]
metadata = [{"category": "science", "year": 2023} for _ in range(100)]
vector_ids = store.store_vectors(vectors, metadata=metadata)

# Search vectors
query_vector = np.random.rand(768)
results = store.search_vectors(query_vector, k=10)

print(f"Stored {len(vector_ids)} vectors")
print(f"Found {len(results)} similar vectors")
```

### Using Convenience Functions

```python
from semantica.vector_store import store_vectors, search_vectors, hybrid_search
from semantica.vector_store import MetadataFilter
import numpy as np

# Store vectors
vectors = [np.random.rand(768) for _ in range(100)]
metadata = [{"category": "science"} for _ in range(100)]
vector_ids = store_vectors(vectors, metadata=metadata, method="default")

# Search vectors
query_vector = np.random.rand(768)
results = search_vectors(query_vector, vectors, vector_ids, k=10, method="default")

# Hybrid search with metadata filter
filter = MetadataFilter().eq("category", "science")
hybrid_results = hybrid_search(
    query_vector, vectors, metadata, vector_ids,
    metadata_filter=filter, k=10, method="default"
)

print(f"Found {len(results)} results")
print(f"Found {len(hybrid_results)} hybrid results")
```

### Using HybridSearch

```python
from semantica.vector_store import HybridSearch, MetadataFilter
import numpy as np

# Create hybrid search
search = HybridSearch()

# Create metadata filter
filter = MetadataFilter().eq("category", "science").gt("year", 2020)

# Perform hybrid search
query_vector = np.random.rand(768)
vectors = [np.random.rand(768) for _ in range(1000)]
metadata = [{"category": "science", "year": 2023} for _ in range(1000)]
vector_ids = [f"vec_{i}" for i in range(1000)]

results = search.search(
    query_vector, vectors, metadata, vector_ids,
    metadata_filter=filter, k=10
)

print(f"Found {len(results)} results")
for result in results[:5]:
    print(f"ID: {result['id']}, Score: {result['score']:.3f}")
```

## Quick Decision Tracking Example

```python
# Set up decision tracking
from semantica.vector_store.decision_vector_methods import set_global_vector_store, quick_decision, find_precedents

set_global_vector_store(vector_store)

# Record a decision
decision_id = quick_decision(
    scenario="Credit limit increase request",
    reasoning="Good payment history",
    outcome="approved",
    confidence=0.85
)

# Find similar decisions
precedents = find_precedents("Credit limit increase", limit=5)
print(f"Found {len(precedents)} similar decisions")
```

## Vector Storage Operations

### Storing Vectors

```python
from semantica.vector_store import VectorStore
import numpy as np

store = VectorStore(backend="faiss", dimension=768)

# Store single batch of vectors
vectors = [np.random.rand(768) for _ in range(1000)]
metadata = [{"category": "science", "year": 2023} for _ in range(1000)]
vector_ids = store.store_vectors(vectors, metadata=metadata)

print(f"Stored {len(vector_ids)} vectors")
print(f"First vector ID: {vector_ids[0]}")
```

### Batch Storage

```python
from semantica.vector_store import VectorStore
import numpy as np

store = VectorStore(backend="faiss", dimension=768)

# Store in batches
batch_size = 100
total_vectors = 10000

for i in range(0, total_vectors, batch_size):
    batch_vectors = [np.random.rand(768) for _ in range(batch_size)]
    batch_metadata = [{"batch": i // batch_size} for _ in range(batch_size)]
    vector_ids = store.store_vectors(batch_vectors, metadata=batch_metadata)
    print(f"Stored batch {i // batch_size + 1}: {len(vector_ids)} vectors")
```

### Updating Vectors

```python
from semantica.vector_store import VectorStore
import numpy as np

store = VectorStore(backend="faiss", dimension=768)

# Store initial vectors
vectors = [np.random.rand(768) for _ in range(100)]
vector_ids = store.store_vectors(vectors)

# Update vectors
new_vectors = [np.random.rand(768) for _ in range(100)]
success = store.update_vectors(vector_ids, new_vectors)

print(f"Updated {len(vector_ids)} vectors: {success}")
```

### Deleting Vectors

```python
from semantica.vector_store import VectorStore
import numpy as np

store = VectorStore(backend="faiss", dimension=768)

# Store vectors
vectors = [np.random.rand(768) for _ in range(100)]
vector_ids = store.store_vectors(vectors)

# Delete some vectors
vectors_to_delete = vector_ids[:10]
success = store.delete_vectors(vectors_to_delete)

print(f"Deleted {len(vectors_to_delete)} vectors: {success}")
```

## Similarity Search

### Basic Similarity Search

```python
from semantica.vector_store import VectorStore
import numpy as np

store = VectorStore(backend="faiss", dimension=768)

# Store vectors
vectors = [np.random.rand(768) for _ in range(1000)]
vector_ids = store.store_vectors(vectors)

# Search for similar vectors
query_vector = np.random.rand(768)
results = store.search_vectors(query_vector, k=10)

print(f"Found {len(results)} similar vectors")
for result in results:
    print(f"ID: {result['id']}, Score: {result['score']:.3f}")
```

### Using VectorRetriever

```python
from semantica.vector_store import VectorRetriever
import numpy as np

retriever = VectorRetriever(backend="faiss")

# Prepare vectors
vectors = [np.random.rand(768) for _ in range(1000)]
vector_ids = [f"vec_{i}" for i in range(1000)]

# Search
query_vector = np.random.rand(768)
results = retriever.search_similar(query_vector, vectors, vector_ids, k=10)

print(f"Found {len(results)} results")
```

### Using VectorManager

```python
from semantica.vector_store import VectorManager

# Create manager
manager = VectorManager()

# Create and register stores
faiss_store = manager.create_store("faiss", {"dimension": 768})
manager.register_store("main_store", "faiss", {"dimension": 768})

# List all stores
stores = manager.list_stores()
print(f"Active stores: {stores}")

# Get store by ID
store = manager.get_store("main_store")

# Get store statistics
stats = manager.get_store_stats("main_store")
print(f"Store stats: {stats}")
```

### Cosine Similarity Search

```python
from semantica.vector_store import VectorStore
import numpy as np

store = VectorStore(backend="faiss", dimension=768, metric="cosine")

# Store normalized vectors
vectors = [np.random.rand(768) for _ in range(1000)]
# Normalize vectors
vectors = [v / np.linalg.norm(v) for v in vectors]
vector_ids = store.store_vectors(vectors)

# Search
query_vector = np.random.rand(768)
query_vector = query_vector / np.linalg.norm(query_vector)
results = store.search_vectors(query_vector, k=10)

print(f"Cosine similarity results: {len(results)}")
```

### L2 Distance Search

```python
from semantica.vector_store import VectorStore
import numpy as np

store = VectorStore(backend="faiss", dimension=768, metric="l2")

# Store vectors
vectors = [np.random.rand(768) for _ in range(1000)]
vector_ids = store.store_vectors(vectors)

# Search
query_vector = np.random.rand(768)
results = store.search_vectors(query_vector, k=10)

print(f"L2 distance results: {len(results)}")
```

## Index Management

### Creating Indexes

```python
from semantica.vector_store import VectorIndexer
import numpy as np

# Create indexer
indexer = VectorIndexer(backend="faiss", dimension=768)

# Create index
vectors = [np.random.rand(768) for _ in range(1000)]
vector_ids = [f"vec_{i}" for i in range(1000)]
index = indexer.create_index(vectors, vector_ids)

print(f"Created index with {len(vector_ids)} vectors")
```

### FAISS Index Types

```python
from semantica.vector_store import FAISSStore
import numpy as np

adapter = FAISSStore(dimension=768)

# Create Flat index (exact search)
flat_index = adapter.create_index(index_type="flat", metric="L2")

# Create IVF index (approximate search)
ivf_index = adapter.create_index(
    index_type="ivf",
    metric="L2",
    nlist=100  # Number of clusters
)

# Create HNSW index (approximate search)
hnsw_index = adapter.create_index(
    index_type="hnsw",
    metric="L2",
    m=16,  # Number of connections
    ef_construction=200
)

# Create PQ index (compressed)
pq_index = adapter.create_index(
    index_type="pq",
    metric="L2",
    m=8  # Number of sub-vectors
)
```

### Index Training

```python
from semantica.vector_store import FAISSStore
import numpy as np

adapter = FAISSStore(dimension=768)

# Training vectors
training_vectors = np.random.rand(10000, 768).astype('float32')

# Create and train IVF index
index = adapter.create_index(
    index_type="ivf",
    metric="L2",
    nlist=100
)

# Train index
adapter.train_index(index, training_vectors)

# Add vectors
vectors = np.random.rand(1000, 768).astype('float32')
adapter.add_vectors(index, vectors, ids=[f"vec_{i}" for i in range(1000)])
```

### Index Persistence

```python
from semantica.vector_store import FAISSStore
import numpy as np

adapter = FAISSStore(dimension=768)

# Create and populate index
index = adapter.create_index(index_type="flat", metric="L2")
vectors = np.random.rand(1000, 768).astype('float32')
adapter.add_vectors(index, vectors, ids=[f"vec_{i}" for i in range(1000)])

# Save index
adapter.save_index(index, "index.faiss")

# Load index
loaded_index = adapter.load_index("index.faiss", dimension=768, index_type="flat")
```

## Hybrid Search

### Basic Hybrid Search

```python
from semantica.vector_store import HybridSearch, MetadataFilter
import numpy as np

search = HybridSearch()

# Prepare data
query_vector = np.random.rand(768)
vectors = [np.random.rand(768) for _ in range(1000)]
metadata = [
    {"category": "science" if i % 2 == 0 else "technology", "year": 2020 + (i % 4)}
    for i in range(1000)
]
vector_ids = [f"vec_{i}" for i in range(1000)]

# Create metadata filter
filter = MetadataFilter().eq("category", "science").gt("year", 2021)

# Perform hybrid search
results = search.search(
    query_vector, vectors, metadata, vector_ids,
    metadata_filter=filter, k=10
)

print(f"Found {len(results)} results")
for result in results:
    print(f"ID: {result['id']}, Score: {result['score']:.3f}, Metadata: {result.get('metadata', {})}")
```

### Metadata Filtering

```python
from semantica.vector_store import MetadataFilter

# Create filter with multiple conditions
filter = MetadataFilter() \
    .eq("category", "science") \
    .gt("year", 2020) \
    .in_list("tags", ["AI", "ML"])

# Test metadata
metadata1 = {"category": "science", "year": 2023, "tags": ["AI", "ML"]}
metadata2 = {"category": "technology", "year": 2023, "tags": ["AI"]}

print(f"Metadata1 matches: {filter.matches(metadata1)}")  # True
print(f"Metadata2 matches: {filter.matches(metadata2)}")  # False
```

### Result Fusion

```python
from semantica.vector_store import SearchRanker
import numpy as np

ranker = SearchRanker(strategy="reciprocal_rank_fusion")

# Multiple result lists
results1 = [
    {"id": "vec_1", "score": 0.9},
    {"id": "vec_2", "score": 0.8},
    {"id": "vec_3", "score": 0.7}
]
results2 = [
    {"id": "vec_2", "score": 0.85},
    {"id": "vec_4", "score": 0.75},
    {"id": "vec_1", "score": 0.7}
]

# Fuse results using RRF
fused = ranker.rank([results1, results2], k=60)

print(f"Fused {len(fused)} results")
for result in fused:
    print(f"ID: {result['id']}, Score: {result['score']:.3f}")
```

### Multi-Source Search

```python
from semantica.vector_store import HybridSearch
import numpy as np

search = HybridSearch()

# Multiple sources
sources = [
    {
        "vectors": [np.random.rand(768) for _ in range(500)],
        "metadata": [{"source": "db1"} for _ in range(500)],
        "ids": [f"db1_vec_{i}" for i in range(500)]
    },
    {
        "vectors": [np.random.rand(768) for _ in range(500)],
        "metadata": [{"source": "db2"} for _ in range(500)],
        "ids": [f"db2_vec_{i}" for i in range(500)]
    }
]

# Search across all sources
query_vector = np.random.rand(768)
results = search.multi_source_search(query_vector, sources, k=10)

print(f"Found {len(results)} results from multiple sources")
```

## Metadata Management

### Storing Metadata

```python
from semantica.vector_store import MetadataStore

store = MetadataStore()

# Store metadata
store.store_metadata("vec_1", {"category": "science", "year": 2023, "tags": ["AI"]})
store.store_metadata("vec_2", {"category": "technology", "year": 2022, "tags": ["ML"]})

# Get metadata
metadata = store.get_metadata("vec_1")
print(f"Metadata: {metadata}")
```

### Metadata Indexing

```python
from semantica.vector_store import MetadataIndex

index = MetadataIndex()

# Index metadata
index.index_metadata("vec_1", {"category": "science", "year": 2023})
index.index_metadata("vec_2", {"category": "science", "year": 2022})
index.index_metadata("vec_3", {"category": "technology", "year": 2023})

# Query by metadata
matching_ids = index.query({"category": "science"}, operator="AND")
print(f"Found {len(matching_ids)} vectors with category='science'")

# Query with multiple conditions
matching_ids = index.query({"category": "science", "year": 2023}, operator="AND")
print(f"Found {len(matching_ids)} vectors matching both conditions")
```

### Metadata Schema

```python
from semantica.vector_store import MetadataSchema

# Define schema
schema = MetadataSchema({
    "category": {"type": str, "required": True},
    "year": {"type": int, "required": True},
    "tags": {"type": list, "required": False}
})

# Validate metadata
metadata1 = {"category": "science", "year": 2023, "tags": ["AI"]}
metadata2 = {"category": "science"}  # Missing required field

print(f"Metadata1 valid: {schema.validate(metadata1)}")  # True
try:
    schema.validate(metadata2)  # Raises ValidationError
except Exception as e:
    print(f"Metadata2 invalid: {e}")
```

### Metadata Querying

```python
from semantica.vector_store import MetadataStore

store = MetadataStore()

# Store metadata
for i in range(100):
    store.store_metadata(
        f"vec_{i}",
        {
            "category": "science" if i % 2 == 0 else "technology",
            "year": 2020 + (i % 4),
            "tags": ["AI"] if i % 3 == 0 else ["ML"]
        }
    )

# Query metadata
vector_ids = store.query_metadata({"category": "science"}, operator="AND")
print(f"Found {len(vector_ids)} vectors with category='science'")

# Query with OR operator
vector_ids = store.query_metadata({"category": "science", "tags": "AI"}, operator="OR")
print(f"Found {len(vector_ids)} vectors matching any condition")
```

## Namespace Management

### Creating Namespaces

```python
from semantica.vector_store import NamespaceManager

manager = NamespaceManager()

# Create namespace
namespace = manager.create_namespace(
    "user1",
    description="User 1 vectors",
    metadata={"owner": "user1", "created": "2024-01-01"}
)

print(f"Created namespace: {namespace.name}")
print(f"Description: {namespace.description}")
```

### Adding Vectors to Namespaces

```python
from semantica.vector_store import NamespaceManager

manager = NamespaceManager()

# Create namespace
manager.create_namespace("user1", description="User 1 vectors")

# Add vectors to namespace
for i in range(100):
    manager.add_vector_to_namespace(f"vec_{i}", "user1")

# Get namespace vectors
vectors = manager.get_namespace_vectors("user1")
print(f"Namespace 'user1' has {len(vectors)} vectors")
```

### Access Control

```python
from semantica.vector_store import NamespaceManager

manager = NamespaceManager()

# Create namespace
namespace = manager.create_namespace("docs", description="Document vectors")

# Set access control
namespace.set_access_control("user1", ["read", "write"])
namespace.set_access_control("user2", ["read"])

# Check permissions
has_read = namespace.has_permission("user1", "read")
has_write = namespace.has_permission("user2", "write")

print(f"User1 has read: {has_read}, write: {has_write}")
print(f"User2 has read: {namespace.has_permission('user2', 'read')}")
print(f"User2 has write: {namespace.has_permission('user2', 'write')}")
```

### Multi-Tenant Support

```python
from semantica.vector_store import NamespaceManager

manager = NamespaceManager()

# Create namespaces for different tenants
manager.create_namespace("tenant1", description="Tenant 1 vectors")
manager.create_namespace("tenant2", description="Tenant 2 vectors")

# Add vectors to each tenant
for i in range(50):
    manager.add_vector_to_namespace(f"t1_vec_{i}", "tenant1")
    manager.add_vector_to_namespace(f"t2_vec_{i}", "tenant2")

# Get tenant-specific vectors
tenant1_vectors = manager.get_namespace_vectors("tenant1")
tenant2_vectors = manager.get_namespace_vectors("tenant2")

print(f"Tenant1: {len(tenant1_vectors)} vectors")
print(f"Tenant2: {len(tenant2_vectors)} vectors")
```

## Store Backends

### FAISS Store

```python
from semantica.vector_store import FAISSStore
import numpy as np

# Create FAISS store
store = FAISSStore(dimension=768)

# Create index
store.create_index(index_type="flat", metric="L2")

# Add vectors
vectors = np.random.rand(1000, 768).astype('float32')
ids = [f"vec_{i}" for i in range(1000)]
store.add_vectors(vectors, ids=ids)

# Search
query_vector = np.random.rand(768).astype('float32')
results = store.search_similar(query_vector, k=10)

print(f"Found {len(results)} similar vectors")
```

### Weaviate Store

```python
from semantica.vector_store import WeaviateStore
import numpy as np

# Create Weaviate store
store = WeaviateStore(url="http://localhost:8080")

# Connect
store.connect()

# Create schema
store.create_schema(
    "Document",
    properties=[{"name": "text", "dataType": "text"}]
)

# Add objects with vectors
objects = [{"text": f"Document {i}"} for i in range(100)]
vectors = [np.random.rand(768).tolist() for _ in range(100)]
object_ids = store.add_objects(objects, vectors=vectors)

# Query
query_vector = np.random.rand(768).tolist()
results = store.query_vectors(
    query_vector,
    limit=10,
    where={"category": "science"}
)

print(f"Found {len(results)} results")
```

### Qdrant Store

```python
from semantica.vector_store import QdrantStore
import numpy as np

# Create Qdrant store
store = QdrantStore(url="http://localhost:6333")

# Connect
store.connect()

# Create collection
collection = store.create_collection("my-collection", dimension=768)

# Upsert vectors
vectors = [np.random.rand(768).tolist() for _ in range(100)]
ids = [f"vec_{i}" for i in range(100)]
payloads = [{"category": "science"} for _ in range(100)]
store.upsert_vectors(collection, vectors, ids, payloads)

# Search
query_vector = np.random.rand(768).tolist()
results = store.search(
    collection,
    query_vector,
    top=10,
    query_filter={"must": [{"key": "category", "match": {"value": "science"}}]}
)

print(f"Found {len(results)} results")
```

### Pinecone Store

```python
from semantica.vector_store import PineconeStore
import numpy as np

# Create Pinecone store
store = PineconeStore(api_key="your-api-key")

# Connect
store.connect()

# Create index
store.create_index("my-index", dimension=768, metric="cosine")

# Upsert vectors
vectors = [np.random.rand(768).tolist() for _ in range(100)]
ids = [f"vec_{i}" for i in range(100)]
metadata = [{"category": "science"} for _ in range(100)]
store.upsert_vectors(vectors, ids, metadata=metadata, namespace="my-namespace")

# Search
query_vector = np.random.rand(768).tolist()
results = store.search_vectors(
    query_vector,
    k=10,
    filter={"category": {"$eq": "science"}},
    namespace="my-namespace"
)

print(f"Found {len(results)} results")
```

### Milvus Store

```python
from semantica.vector_store import MilvusStore
import numpy as np

# Create Milvus store
store = MilvusStore(host="localhost", port="19530")

# Connect
store.connect()

# Create collection
collection = store.create_collection(
    "my-collection",
    dimension=768,
    metric_type="L2"
)

# Insert vectors
vectors = np.random.rand(100, 768).astype('float32')
ids = [f"vec_{i}" for i in range(100)]
store.insert_vectors(collection, vectors, ids)

# Search
query_vector = np.random.rand(768).astype('float32')
results = store.search(collection, query_vector, top_k=10)

print(f"Found {len(results)} results")
```

## Algorithms and Methods

### Vector Storage Algorithms

#### Vector Storage
**Algorithm**: ID generation and vector normalization

1. **ID Generation**: Generate unique IDs (sequential: vec_0, vec_1, ... or UUID-based)
2. **Vector Normalization**: Optional L2 normalization (v / ||v||) for cosine similarity
3. **Metadata Association**: Map vector IDs to metadata dictionaries
4. **Index Update**: Update vector index after storage

**Time Complexity**: O(n) where n = number of vectors
**Space Complexity**: O(n × d) where d = vector dimension

```python
# Vector storage
vector_ids = store.store_vectors(vectors, metadata=metadata_list)
```

#### Batch Storage
**Algorithm**: Chunking algorithm for large datasets

1. **Batch Creation**: Divide vectors into fixed-size batches
2. **Batch Processing**: Process each batch sequentially
3. **Progress Tracking**: Track stored count, progress percentage
4. **Error Handling**: Handle errors per batch, continue on failure

**Time Complexity**: O(n) where n = total vectors
**Space Complexity**: O(b × d) where b = batch size, d = dimension

### Similarity Search Algorithms

#### Cosine Similarity
**Algorithm**: Normalized dot product calculation

1. **Vector Normalization**: Normalize query and database vectors (L2 norm)
2. **Dot Product**: Calculate dot(v1, v2) for all vectors
3. **Similarity Score**: Similarity = dot(v1, v2) / (||v1|| × ||v2||)
4. **Top-k Selection**: Argsort similarities in descending order, select top k

**Time Complexity**: O(n × d) where n = vectors, d = dimension
**Space Complexity**: O(n) for similarities

```python
# Cosine similarity search
results = store.search_vectors(query_vector, k=10)
```

#### L2 Distance
**Algorithm**: Euclidean distance calculation

1. **Distance Calculation**: distance = sqrt(sum((v1 - v2)²))
2. **Distance-to-Similarity**: similarity = 1 / (1 + distance)
3. **Top-k Selection**: Argsort distances in ascending order, select top k

**Time Complexity**: O(n × d) where n = vectors, d = dimension
**Space Complexity**: O(n) for distances

#### Approximate Nearest Neighbor (ANN)
**Algorithm**: FAISS approximate search algorithms

**FAISS IVF**:
1. **k-means Clustering**: Cluster vectors into nlist cells
2. **Inverted File**: Build inverted file mapping cells to vectors
3. **Approximate Search**: Search nprobe cells, compute exact distances within cells

**FAISS HNSW**:
1. **Graph Construction**: Build multi-layer graph with connections
2. **Greedy Search**: Start from entry point, traverse graph to nearest neighbors
3. **Approximate Search**: Configurable ef_search for accuracy/speed tradeoff

**Time Complexity**: O(log n) to O(n) depending on index type and parameters
**Space Complexity**: O(n × d) for vectors, O(n × m) for HNSW graph

```python
# ANN search with FAISS
adapter = FAISSStore(dimension=768)
index = adapter.create_index(index_type="ivf", nlist=100)
results = adapter.search(index, query_vector, k=10)
```

### Index Construction Algorithms

#### FAISS Flat Index
**Algorithm**: Brute force exact search

1. **No Training**: Direct vector storage, no preprocessing
2. **Exact Search**: Compute all distances, select top k
3. **Full Storage**: Store all vectors in memory

**Time Complexity**: O(n × d) for search
**Space Complexity**: O(n × d) for storage

#### FAISS IVF Index
**Algorithm**: Inverted file index with k-means

1. **Training**: k-means clustering on training vectors (nlist clusters)
2. **Cell Assignment**: Assign each vector to nearest cluster center
3. **Inverted File**: Build mapping from cluster to vectors
4. **Search**: Search nprobe clusters, compute exact distances

**Time Complexity**: O(n × d × log(nlist)) for training, O(nprobe × (n/nlist) × d) for search
**Space Complexity**: O(n × d) for vectors, O(nlist × d) for cluster centers

#### FAISS HNSW Index
**Algorithm**: Hierarchical navigable small world graph

1. **Graph Construction**: Build multi-layer graph (m connections per node)
2. **Layer Assignment**: Assign vectors to layers probabilistically
3. **Greedy Search**: Start from entry point, traverse graph greedily
4. **Connection Management**: Maintain connections to nearest neighbors

**Time Complexity**: O(log n) for search with ef_search parameter
**Space Complexity**: O(n × m) for graph connections

### Hybrid Search Algorithms

#### Vector Similarity + Metadata Filtering
**Algorithm**: Two-stage filtering and search

1. **Metadata Filtering**: Apply metadata filter conditions first
2. **Vector Search**: Perform vector similarity search on filtered set
3. **Result Combination**: Combine filtered metadata with search results

**Time Complexity**: O(m × f) for filtering + O(n × d) for search where m = metadata count, f = filter conditions, n = filtered vectors
**Space Complexity**: O(n) for filtered vectors

```python
# Hybrid search
filter = MetadataFilter().eq("category", "science")
results = hybrid_search(query_vector, vectors, metadata, vector_ids, metadata_filter=filter, k=10)
```

#### Reciprocal Rank Fusion (RRF)
**Algorithm**: Result fusion using reciprocal ranks

1. **Rank Collection**: Collect ranks of each result from all result lists
2. **Score Calculation**: score = sum(1 / (k + rank)) for each result across all lists
3. **Result Ranking**: Sort results by RRF score in descending order
4. **Top-k Selection**: Select top k results after fusion

**Time Complexity**: O(r × l) where r = results per list, l = number of lists
**Space Complexity**: O(r × l) for result storage

```python
# RRF fusion
ranker = SearchRanker(strategy="reciprocal_rank_fusion")
fused = ranker.rank([results1, results2], k=60)
```

#### Weighted Average Fusion
**Algorithm**: Weighted sum of scores

1. **Score Collection**: Collect scores for each result from all lists
2. **Weighted Sum**: weighted_score = sum(score × weight) for each result
3. **Result Ranking**: Sort results by weighted score
4. **Top-k Selection**: Select top k results

**Time Complexity**: O(r × l) where r = results per list, l = number of lists
**Space Complexity**: O(r × l) for result storage

### Metadata Management Algorithms

#### Metadata Indexing
**Algorithm**: Inverted index per field

1. **Field Indexing**: Create inverted index for each metadata field
2. **Value Mapping**: Map field values to sets of vector IDs
3. **List Handling**: Index each item in list values
4. **Fast Lookup**: O(1) lookup per field-value pair

**Time Complexity**: O(m × f) where m = metadata count, f = fields per metadata
**Space Complexity**: O(m × f) for indexes

```python
# Metadata indexing
index = MetadataIndex()
index.index_metadata("vec_1", {"category": "science", "year": 2023})
matching_ids = index.query({"category": "science"})
```

#### Metadata Filtering
**Algorithm**: Condition-based filtering

1. **Condition Evaluation**: Evaluate each filter condition (eq, ne, gt, gte, lt, lte, in, contains)
2. **AND/OR Combination**: Combine conditions using AND (intersection) or OR (union)
3. **Result Set Construction**: Build set of matching vector IDs

**Time Complexity**: O(m × c) where m = metadata count, c = conditions
**Space Complexity**: O(m) for result set

```python
# Metadata filtering
filter = MetadataFilter().eq("category", "science").gt("year", 2020)
matching = [meta for meta in metadata if filter.matches(meta)]
```

### Namespace Management Algorithms

#### Namespace Isolation
**Algorithm**: Vector-to-namespace mapping

1. **Mapping Storage**: Dictionary mapping vector_id -> namespace
2. **Namespace Organization**: Group vectors by namespace
3. **Access Control**: Store permissions per namespace-entity pair
4. **Isolation Enforcement**: Filter operations by namespace

**Time Complexity**: O(1) for vector-to-namespace lookup
**Space Complexity**: O(n) where n = vectors

```python
# Namespace isolation
manager.add_vector_to_namespace("vec_1", "user1")
vectors = manager.get_namespace_vectors("user1")
```

### Methods

#### VectorStore Methods

- `store_vectors(vectors, metadata, **options)`: Store vectors with metadata
- `search_vectors(query_vector, k, **options)`: Search for similar vectors
- `update_vectors(vector_ids, new_vectors, **options)`: Update existing vectors
- `delete_vectors(vector_ids, **options)`: Delete vectors
- `get_vector(vector_id)`: Get vector by ID
- `get_metadata(vector_id)`: Get metadata by vector ID

#### VectorIndexer Methods

- `create_index(vectors, ids, **options)`: Create vector index
- `update_index(index, new_vectors, **options)`: Update existing index
- `optimize_index(index, **options)`: Optimize index for performance

#### VectorRetriever Methods

- `search_similar(query_vector, vectors, ids, k, **options)`: Search for similar vectors
- `search_by_metadata(metadata_filters, vectors, metadata, **options)`: Search by metadata
- `search_hybrid(query_vector, metadata_filters, vectors, metadata, **options)`: Hybrid search

## Decision Tracking

The enhanced vector store provides comprehensive decision tracking capabilities with hybrid search, explainable AI, and KG algorithm integration.

### Decision Embedding Pipeline

```python
from semantica.vector_store import DecisionEmbeddingPipeline, VectorStore
import numpy as np

# Initialize vector store and pipeline
vector_store = VectorStore(backend="inmemory", dimension=384)
pipeline = DecisionEmbeddingPipeline(
    vector_store=vector_store,
    semantic_weight=0.7,
    structural_weight=0.3,
    use_graph_features=True
)

# Process a decision
decision_data = {
    "scenario": "Credit limit increase for premium customer",
    "reasoning": "Excellent payment history and high credit score",
    "outcome": "approved",
    "confidence": 0.92,
    "entities": ["customer_123", "premium_segment", "credit_card"],
    "category": "credit_approval",
    "amount": 50000,
    "risk_level": "low"
}

# Generate embeddings
embeddings = pipeline.generate_decision_embeddings(decision_data)
print(f"Semantic embedding: {len(embeddings['semantic'])} dimensions")
print(f"Structural embedding: {len(embeddings['structural'])} dimensions")
print(f"Combined embedding: {len(embeddings['combined'])} dimensions")
```

### Batch Decision Processing

```python
# Process multiple decisions
decisions = [
    {
        "scenario": "Credit limit increase request",
        "reasoning": "Good payment history",
        "outcome": "approved",
        "confidence": 0.85,
        "entities": ["customer_456"],
        "category": "credit_approval"
    },
    {
        "scenario": "Fraud detection alert",
        "reasoning": "Suspicious transaction pattern",
        "outcome": "blocked",
        "confidence": 0.95,
        "entities": ["transaction_789", "customer_456"],
        "category": "fraud_detection"
    }
]

# Batch process decisions
batch_results = pipeline.process_decision_batch(decisions, batch_size=2)
print(f"Processed {len(batch_results)} decisions")

for result in batch_results:
    print(f"Decision ID: {result['decision_id']}")
    print(f"Vector ID: {result['vector_id']}")
    print(f"Embedding dimensions: {len(result['combined_embedding'])}")
```

### Decision Vector Operations

```python
from semantica.vector_store.decision_vector_methods import (
    store_decision, search_decisions, get_decision_embeddings,
    filter_decisions, batch_decisions
)

# Store a decision
decision_id = store_decision(
    scenario="Loan application assessment",
    reasoning="Stable income but high debt-to-income ratio",
    outcome="approved_with_conditions",
    confidence=0.82,
    entities=["applicant_555", "loan_mortgage"],
    category="risk_assessment",
    vector_store=vector_store
)

# Search decisions
results = search_decisions(
    query="Loan assessment with conditions",
    limit=5,
    vector_store=vector_store
)

# Filter decisions by criteria
filtered = filter_decisions(
    category="risk_assessment",
    confidence_min=0.8,
    outcome="approved",
    vector_store=vector_store
)

print(f"Found {len(results)} decisions")
print(f"Filtered {len(filtered)} decisions")
```

## Hybrid Similarity for Decisions

The `HybridSimilarityCalculator` provides enhanced similarity calculations combining semantic and structural embeddings.

### Basic Hybrid Similarity

```python
from semantica.vector_store import HybridSimilarityCalculator
import numpy as np

# Initialize calculator
calculator = HybridSimilarityCalculator(
    semantic_weight=0.7,
    structural_weight=0.3,
    similarity_metric="cosine"
)

# Calculate similarity between decisions
semantic1 = np.random.rand(384)
semantic2 = np.random.rand(384)
structural1 = np.random.rand(128)
structural2 = np.random.rand(128)

similarity = calculator.calculate_hybrid_similarity(
    semantic1, semantic2, structural1, structural2
)

print(f"Hybrid similarity: {similarity:.3f}")
```

### Batch Similarity Calculation

```python
# Calculate similarities for multiple decision pairs
decision_pairs = [
    (semantic1, semantic2, structural1, structural2),
    (semantic3, semantic4, structural3, structural4),
    (semantic5, semantic6, structural5, structural6)
]

similarities = calculator.calculate_batch_similarity(decision_pairs)
print(f"Batch similarities: {similarities}")

# Calculate similarity matrix
semantic_embeddings = [semantic1, semantic2, semantic3]
structural_embeddings = [structural1, structural2, structural3]

similarity_matrix = calculator.calculate_similarity_matrix(
    semantic_embeddings, structural_embeddings
)

print(f"Similarity matrix: {similarity_matrix.shape}")
```

### Additional Similarity Metrics

```python
# Try different similarity metrics
metrics = ["cosine", "pearson", "euclidean", "dot_product"]

for metric in metrics:
    calculator = HybridSimilarityCalculator(
        semantic_weight=0.6,
        structural_weight=0.4,
        similarity_metric=metric
    )
    
    similarity = calculator.calculate_hybrid_similarity(
        semantic1, semantic2, structural1, structural2
    )
    
    print(f"{metric}: {similarity:.3f}")
```

### Context-Enhanced Similarity

```python
# Calculate similarity with context enhancement
context_info = {
    "shared_entities": ["customer", "credit"],
    "entity_weights": {"customer": 0.8, "credit": 0.6},
    "relationship_strength": 0.7
}

enhanced_similarity = calculator.calculate_context_enhanced_similarity(
    semantic1, semantic2, structural1, structural2, context_info
)

print(f"Context-enhanced similarity: {enhanced_similarity:.3f}")
```

## Convenience Functions

The vector store module provides convenient one-liner functions for common decision tracking operations.

### Quick Decision Operations

```python
from semantica.vector_store.decision_vector_methods import (
    quick_decision, find_precedents, explain, similar_to,
    set_global_vector_store, get_global_vector_store
)

# Set global vector store (once per application)
set_global_vector_store(vector_store)

# Quick decision recording
decision_id = quick_decision(
    scenario="Credit limit increase request",
    reasoning="Good payment history",
    outcome="approved"
)

print(f"Quick decision recorded: {decision_id}")
```

### Finding Precedents

```python
# Find decision precedents
precedents = find_precedents(
    query="Credit limit increase",
    limit=5,
    filters={"category": "credit_approval"},
    use_hybrid_search=True
)

print(f"Found {len(precedents)} precedents")
for precedent in precedents:
    print(f"Score: {precedent['score']:.3f}")
    print(f"Outcome: {precedent['outcome']}")
```

### Decision Explanation

```python
# Explain a decision
explanation = explain(
    decision_id,
    include_paths=True,
    include_confidence=True,
    include_weights=True
)

print(f"Decision explanation:")
print(f"Scenario: {explanation['scenario']}")
print(f"Reasoning: {explanation['reasoning']}")
print(f"Outcome: {explanation['outcome']}")
print(f"Confidence: {explanation['confidence']}")
```

### Finding Similar Decisions

```python
# Find similar decisions
similar = similar_to(
    query="High-risk credit assessment",
    limit=10,
    semantic_weight=0.8,
    structural_weight=0.2
)

print(f"Found {len(similar)} similar decisions")
for decision in similar:
    print(f"Category: {decision['category']}")
    print(f"Risk level: {decision.get('risk_level', 'unknown')}")
```

### Batch Operations

```python
# Batch process decisions
batch_data = [
    {"scenario": f"Decision {i}", "reasoning": f"Reason {i}", "outcome": "approved"}
    for i in range(10)
]

batch_results = batch_decisions(batch_data)
print(f"Batch processed {len(batch_results)} decisions")

# Filter decisions
high_confidence = filter_decisions(confidence_min=0.8)
credit_decisions = filter_decisions(category="credit_approval")

print(f"High confidence decisions: {len(high_confidence)}")
print(f"Credit decisions: {len(credit_decisions)}")
```

### Entity-Based Search

```python
from semantica.vector_store.decision_vector_methods import search_by_entities

# Search decisions by entities
entity_decisions = search_by_entities(
    entities=["customer_123", "premium_segment"],
    limit=5
)

print(f"Found {len(entity_decisions)} decisions for entities")
```

### Decision Context

```python
from semantica.vector_store.decision_vector_methods import get_decision_context

# Get comprehensive decision context
context = get_decision_context(
    decision_id,
    depth=2,
    include_entities=True,
    include_policies=True
)

print(f"Decision context with {len(context.related_entities)} entities")
print(f"Related relationships: {len(context.related_relationships)}")
```

### Real-World Examples

```python
# Banking decision workflow
banking_decision = quick_decision(
    scenario="Mortgage application approval",
    reasoning="Strong credit score (750), stable employment, 20% down payment",
    outcome="approved",
    confidence=0.94,
    entities=["applicant_001", "mortgage_30yr", "property_main"],
    category="mortgage_approval",
    loan_amount=350000,
    credit_score=750
)

# Find similar mortgage decisions
mortgage_precedents = find_precedents(
    query="Mortgage with good credit",
    limit=5,
    filters={"category": "mortgage_approval"}
)

# Explain the decision
mortgage_explanation = explain(banking_decision)
print(f"Mortgage decision: {mortgage_explanation['outcome']}")

# Insurance decision workflow
insurance_decision = quick_decision(
    scenario="Auto insurance claim approval",
    reasoning="Clear liability, reasonable repair costs, no prior claims",
    outcome="approved",
    confidence=0.96,
    entities=["claim_auto_001", "driver_safe", "policy_active"],
    category="auto_insurance",
    claim_amount=2500
)

# Find similar insurance claims
insurance_precedents = find_precedents(
    query="Auto claim with clear liability",
    limit=5,
    filters={"category": "auto_insurance"}
)

print(f"Found {len(insurance_precedents)} similar insurance claims")
```

#### HybridSearch Methods

- `search(query_vector, vectors, metadata, vector_ids, k, metadata_filter, **options)`: Perform hybrid search
- `multi_source_search(query_vector, sources, k, **options)`: Search across multiple sources
- `filter_by_metadata(results, metadata_filter)`: Filter results by metadata

#### MetadataStore Methods

- `store_metadata(vector_id, metadata)`: Store metadata for vector
- `get_metadata(vector_id)`: Get metadata for vector
- `query_metadata(conditions, operator)`: Query vectors by metadata conditions
- `update_metadata(vector_id, metadata)`: Update metadata
- `delete_metadata(vector_id)`: Delete metadata

#### NamespaceManager Methods

- `create_namespace(name, description, metadata, **options)`: Create namespace
- `delete_namespace(name)`: Delete namespace
- `add_vector_to_namespace(vector_id, namespace_name)`: Add vector to namespace
- `remove_vector_from_namespace(vector_id, namespace_name)`: Remove vector from namespace
- `get_namespace_vectors(namespace_name)`: Get all vectors in namespace
- `get_namespace(namespace_name)`: Get namespace object

#### Convenience Functions

- `store_vectors(vectors, metadata, method, **options)`: Store vectors wrapper
- `search_vectors(query_vector, vectors, vector_ids, k, method, **options)`: Search vectors wrapper
- `update_vectors(vector_ids, new_vectors, method, **options)`: Update vectors wrapper
- `delete_vectors(vector_ids, method, **options)`: Delete vectors wrapper
- `create_index(vectors, ids, method, **options)`: Create index wrapper
- `hybrid_search(query_vector, vectors, metadata, vector_ids, k, metadata_filter, method, **options)`: Hybrid search wrapper
- `filter_metadata(metadata, filter_conditions, operator, method, **options)`: Filter metadata wrapper
- `manage_namespace(namespace_name, operation, **options)`: Namespace management wrapper

## Configuration

### Environment Variables

```bash
# Vector store configuration
export VECTOR_STORE_DEFAULT_BACKEND=faiss
export VECTOR_STORE_DIMENSION=768
export VECTOR_STORE_BATCH_SIZE=1000
export VECTOR_STORE_INDEX_TYPE=flat
export VECTOR_STORE_METRIC=cosine
export VECTOR_STORE_ENABLE_HYBRID_SEARCH=true
export VECTOR_STORE_NAMESPACE=default

# FAISS configuration
export VECTOR_STORE_FAISS_INDEX_TYPE=flat

# Weaviate configuration
export VECTOR_STORE_WEAVIATE_URL=http://localhost:8080

# Qdrant configuration
export VECTOR_STORE_QDRANT_URL=http://localhost:6333

# Milvus configuration
export VECTOR_STORE_MILVUS_HOST=localhost
export VECTOR_STORE_MILVUS_PORT=19530
```

### Programmatic Configuration

```python
from semantica.vector_store.config import vector_store_config

# Get configuration
backend = vector_store_config.get("default_backend", default="faiss")
dimension = vector_store_config.get("dimension", default=768)

# Set configuration
vector_store_config.set("default_backend", "faiss")
vector_store_config.set("dimension", 768)

# Update with dictionary
vector_store_config.update({
    "default_backend": "faiss",
    "dimension": 768,
    "batch_size": 1000
})
```

### Configuration File (YAML)

```yaml
# config.yaml
vector_store:
  default_backend: faiss
  dimension: 768
  batch_size: 1000
  index_type: flat
  metric: cosine
  enable_hybrid_search: true
  default_namespace: default
  faiss_index_type: flat
  weaviate_url: http://localhost:8080
  qdrant_url: http://localhost:6333
  milvus_host: localhost
  milvus_port: 19530
```

## Complete Examples

### Complete Vector Store Pipeline

```python
from semantica.vector_store import (
    VectorStore,
    HybridSearch,
    MetadataFilter,
    store_vectors,
    search_vectors,
    hybrid_search
)
import numpy as np

# 1. Create vector store
store = VectorStore(backend="faiss", dimension=768)

# 2. Generate and store vectors
vectors = [np.random.rand(768) for _ in range(10000)]
metadata = [
    {"category": "science" if i % 2 == 0 else "technology", "year": 2020 + (i % 4)}
    for i in range(10000)
]
vector_ids = store_vectors(vectors, metadata=metadata)

# 3. Create metadata filter
filter = MetadataFilter().eq("category", "science").gt("year", 2021)

# 4. Perform hybrid search
query_vector = np.random.rand(768)
results = hybrid_search(
    query_vector, vectors, metadata, vector_ids,
    metadata_filter=filter, k=10
)

print(f"Stored {len(vector_ids)} vectors")
print(f"Found {len(results)} hybrid search results")
```

### Multi-Backend Vector Store

```python
from semantica.vector_store import FAISSStore, WeaviateStore
import numpy as np

# Local FAISS store
faiss_store = FAISSStore(dimension=768)
faiss_index = faiss_store.create_index(index_type="flat", metric="L2")
faiss_vectors = np.random.rand(1000, 768).astype('float32')
faiss_store.add_vectors(faiss_index, faiss_vectors, ids=[f"faiss_{i}" for i in range(1000)])

# Self-hosted Weaviate store
weaviate_store = WeaviateStore(url="http://localhost:8080")
weaviate_store.connect()
weaviate_index = weaviate_store.create_index("my-index", dimension=768)
weaviate_vectors = [np.random.rand(768).tolist() for _ in range(1000)]
weaviate_store.upsert_vectors(weaviate_vectors, [f"weaviate_{i}" for i in range(1000)])

# Search both
query_vector = np.random.rand(768)
faiss_results = faiss_store.search(faiss_index, query_vector, k=10)
weaviate_results = weaviate_store.query_vectors(query_vector, top_k=10)
```

### Hybrid Search with Custom Ranking

```python
from semantica.vector_store import HybridSearch, SearchRanker, MetadataFilter
import numpy as np

# Create hybrid search with custom ranker
ranker = SearchRanker(strategy="weighted_average")
search = HybridSearch(ranking_strategy="weighted_average")

# Prepare data
query_vector = np.random.rand(768)
vectors = [np.random.rand(768) for _ in range(1000)]
metadata = [{"category": "science", "year": 2023} for _ in range(1000)]
vector_ids = [f"vec_{i}" for i in range(1000)]

# Create filter
filter = MetadataFilter().eq("category", "science")

# Perform search
results = search.search(
    query_vector, vectors, metadata, vector_ids,
    metadata_filter=filter, k=10
)

# Custom ranking with weights
results1 = search.search(query_vector, vectors[:500], metadata[:500], vector_ids[:500], k=10)
results2 = search.search(query_vector, vectors[500:], metadata[500:], vector_ids[500:], k=10)

fused = ranker.rank([results1, results2], weights=[0.7, 0.3])
print(f"Fused {len(fused)} results with weighted average")
```

### Namespace-Based Multi-Tenant System

```python
from semantica.vector_store import NamespaceManager, VectorStore
import numpy as np

# Create namespace manager
namespace_manager = NamespaceManager()

# Create namespaces for tenants
namespace_manager.create_namespace("tenant1", description="Tenant 1")
namespace_manager.create_namespace("tenant2", description="Tenant 2")

# Create vector store
store = VectorStore(backend="faiss", dimension=768)

# Store vectors for each tenant
for tenant in ["tenant1", "tenant2"]:
    vectors = [np.random.rand(768) for _ in range(1000)]
    vector_ids = store.store_vectors(vectors)
    
    # Add to namespace
    for vec_id in vector_ids:
        namespace_manager.add_vector_to_namespace(vec_id, tenant)

# Tenant-specific search
tenant1_vectors = namespace_manager.get_namespace_vectors("tenant1")
query_vector = np.random.rand(768)
# Search only tenant1 vectors
results = store.search_vectors(query_vector, k=10)
tenant1_results = [r for r in results if r['id'] in tenant1_vectors]
```

### Custom Method Registration

```python
from semantica.vector_store.registry import method_registry
from semantica.vector_store import store_vectors

# Register custom store method
def custom_store_vectors(vectors, metadata=None, **options):
    # Custom logic (e.g., normalization)
    import numpy as np
    normalized_vectors = [v / np.linalg.norm(v) for v in vectors]
    # Call default implementation
    from semantica.vector_store.methods import _get_store
    store = _get_store()
    return store.store_vectors(normalized_vectors, metadata=metadata, **options)

method_registry.register("store", "normalized", custom_store_vectors)

# Use custom method
vector_ids = store_vectors(vectors, metadata=metadata, method="normalized")
```

### SQLite Vector Store (sqlite-vec)

The SQLite vector store backend uses the `sqlite-vec` extension to provide a lightweight, embedded, yet fully persistent vector store. It is ideal for local development, small-to-medium datasets, and embedded applications where setting up a separate PostgreSQL/pgvector instance is not desired.

#### Installation

Install Semantica with SQLite vector store dependencies:

```bash
pip install semantica[vectorstore-sqlite]
```

#### Usage Example

```python
from semantica.vector_store import VectorStore
import numpy as np

# Initialize the vector store using the 'sqlite' backend
# The 'db_path' parameter points to the SQLite database file on disk.
# Use ':memory:' for a transient, in-memory store.
store = VectorStore(
    backend="sqlite",
    config={
        "db_path": "my_vector_database.db",
        "table_name": "documents",
        "dimension": 128,
        "distance_metric": "cosine", # Supported metrics: 'cosine', 'l2'
        "use_wal": True # Optional: enable WAL journal mode + NORMAL synchronous
                         # for better write concurrency (default: False)
    }
)

# Store vectors with metadata
vectors = [np.random.rand(128).astype(np.float32) for _ in range(5)]
metadata = [
    {"category": "ai", "public": True},
    {"category": "finance", "public": False},
    {"category": "ai", "public": False},
    {"category": "healthcare", "public": True},
    {"category": "finance", "public": True}
]
ids = store.store_vectors(vectors, metadata=metadata)

# Search vectors with metadata filtering
query = np.random.rand(128).astype(np.float32)
results = store.search_vectors(
    query,
    k=2,
    filter={"category": "ai"}
)

for r in results:
    print(f"ID: {r['id']}, Score: {r['score']}, Metadata: {r['metadata']}")

# Close the database connection when done
# (Recommended on Windows to release file handles)
store._backend_store.close()
```

## Best Practices

1. **Vector Storage**:
   - Normalize vectors for cosine similarity
   - Use batch operations for large datasets
   - Associate metadata at storage time
   - Validate vector dimensions before storage

2. **Similarity Search**:
   - Choose appropriate metric (cosine for normalized, L2 for distance)
   - Use approximate indices (IVF, HNSW) for large datasets
   - Set appropriate k value (not too large)
   - Cache query vectors when possible

3. **Index Management**:
   - Train indices on representative data
   - Choose index type based on dataset size and accuracy requirements
   - Optimize index parameters (nlist for IVF, m for HNSW)
   - Persist indices for reuse

4. **Hybrid Search**:
   - Apply metadata filters before vector search for efficiency
   - Use RRF for multi-source fusion
   - Tune ranking parameters (k for RRF, weights for weighted average)
   - Combine complementary filters

5. **Metadata Management**:
   - Index frequently queried fields
   - Use schema validation for data quality
   - Keep metadata consistent with vectors
   - Use appropriate operators (AND/OR)

6. **Namespace Management**:
   - Use namespaces for multi-tenant isolation
   - Set appropriate access controls
   - Monitor namespace statistics
   - Clean up unused namespaces

7. **Performance**:
   - Use batch operations when possible
   - Choose appropriate index type for use case
   - Normalize vectors for cosine similarity
   - Cache frequently accessed vectors

8. **Error Handling**:
   - Validate vector dimensions
   - Handle missing metadata gracefully
   - Check namespace existence before operations
   - Handle adapter connection failures

9. **Configuration**:
   - Use environment variables for deployment
   - Use config files for development
   - Set appropriate defaults
   - Document configuration options

10. **Testing**:
    - Test with sample data first
    - Validate search results
    - Test metadata filtering
    - Test namespace isolation
    - Monitor performance metrics

