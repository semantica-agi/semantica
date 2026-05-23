---
title: "Embeddings Module"
description: "Text and graph embedding generation — Sentence-Transformers, FastEmbed, OpenAI, BGE, LlamaStore, with pooling strategies and graph embedding managers."
icon: "vector-square"
---

`semantica.embeddings` converts text and graph structures into dense vectors for semantic search, entity resolution, and GraphRAG retrieval. A single provider-agnostic API abstracts Sentence-Transformers, FastEmbed, OpenAI, BGE, and Ollama.

## What You Get

- **`EmbeddingGenerator`** — main entry point, provider-agnostic text embedding with batching
- **`TextEmbedder`** — text-specific embedding with automatic batching and disk caching
- **`GraphEmbeddingManager`** — node and subgraph embeddings for structural similarity
- **`VectorEmbeddingManager`** — full embedding lifecycle for vector store integration
- **Provider stores** — `OpenAIStore`, `BGEStore`, `FastEmbedStore`, `LlamaStore`, `ProviderStoreFactory`
- **Pooling strategies** — Mean, Max, CLS, Attention, Hierarchical pooling

## EmbeddingGenerator

Main entry point — handles provider selection and batching automatically:

```python
from semantica.embeddings import EmbeddingGenerator

# Sentence-Transformers (default, free, local)
generator = EmbeddingGenerator(model="sentence-transformers")
embeddings = generator.generate(["Text 1", "Text 2"])

# Specific BGE model
generator = EmbeddingGenerator(model="BAAI/bge-large-en-v1.5")
embeddings = generator.generate(texts)

# OpenAI
import os
generator = EmbeddingGenerator(
    model="openai",
    model_name="text-embedding-3-small",
    api_key=os.getenv("OPENAI_API_KEY")
)

# FastEmbed (fast, CPU-optimized)
generator = EmbeddingGenerator(model="fastembed")
```

### Supported Models

| Provider | Model | Dimension | Notes |
| -------- | ----- | --------- | ----- |
| `sentence-transformers` | `all-MiniLM-L6-v2` | 384 | Default, fast, free |
| `sentence-transformers` | `all-mpnet-base-v2` | 768 | Higher quality |
| `bge` | `BAAI/bge-large-en-v1.5` | 1024 | State-of-the-art retrieval |
| `fastembed` | `BAAI/bge-small-en-v1.5` | 384 | Fast, CPU-optimized |
| `openai` | `text-embedding-3-small` | 1536 | OpenAI API |
| `openai` | `text-embedding-3-large` | 3072 | OpenAI API, highest quality |
| `llama` | any Ollama model | varies | Fully local inference |

## TextEmbedder

Specialized for text with automatic batching and optional disk cache:

```python
from semantica.embeddings import TextEmbedder

embedder = TextEmbedder(model="sentence-transformers", cache_dir=".emb_cache")

# Single text
embedding = embedder.embed("Hello world")

# Batch — processes automatically in chunks
embeddings = embedder.embed_batch(
    ["Text 1", "Text 2", ..., "Text 10000"],
    batch_size=128,
    show_progress=True
)
```

## Provider Stores

Each provider implements the `ProviderStore` interface and can be used independently:

```python
from semantica.embeddings import (
    OpenAIStore, BGEStore, FastEmbedStore, LlamaStore,
    ProviderStoreFactory
)

# OpenAI
store = OpenAIStore(api_key=os.getenv("OPENAI_API_KEY"), model="text-embedding-3-small")
embedding = store.embed("Hello world")

# BGE (Sentence-Transformers wrapper)
store = BGEStore(model="BAAI/bge-large-en-v1.5")
embedding = store.embed("Hello world")

# FastEmbed
store = FastEmbedStore(model="BAAI/bge-small-en-v1.5")
embedding = store.embed("Hello world")

# LlamaStore (Ollama — fully local)
store = LlamaStore(model="llama3.2", base_url="http://localhost:11434")
embedding = store.embed("Hello world")

# Auto-select from config
store = ProviderStoreFactory.create(provider="openai", model="text-embedding-3-small")
```

## Pooling Strategies

Control how token-level embeddings are aggregated into a single vector:

```python
from semantica.embeddings import (
    MeanPooling, MaxPooling, CLSPooling,
    AttentionPooling, HierarchicalPooling, PoolingStrategyFactory
)

# Mean pooling — default, best for most tasks
pooler = MeanPooling()
pooled = pooler.pool(token_embeddings)

# Max pooling — captures strongest activated features
pooler = MaxPooling()

# CLS token — good for classification tasks
pooler = CLSPooling()

# Attention-weighted pooling
pooler = AttentionPooling()

# Hierarchical: chunk-level → global mean (best for long documents)
pooler = HierarchicalPooling(chunk_size=512)

# Create from config string
pooler = PoolingStrategyFactory.create(strategy="mean")
```

## GraphEmbeddingManager

Embed graph nodes and subgraphs for structural similarity and GraphRAG context:

```python
from semantica.embeddings import GraphEmbeddingManager

manager = GraphEmbeddingManager(
    text_embedder=TextEmbedder(model="sentence-transformers"),
    graph_store=graph_store
)

# Embed all nodes in the graph
node_embeddings = manager.embed_nodes(kg)

# Embed a subgraph centered on a node (for GraphRAG context)
subgraph_embedding = manager.embed_subgraph(
    kg, center_node="Apple Inc.", hops=2
)

# Find semantically similar nodes
similar = manager.find_similar_nodes("apple_inc", top_k=5)
```

## VectorEmbeddingManager

Manages the full embedding lifecycle — from raw text to stored, searchable vectors:

```python
from semantica.embeddings import VectorEmbeddingManager
from semantica.vector_store import VectorStore

vector_store = VectorStore(backend="faiss", dimension=768)

manager = VectorEmbeddingManager(
    embedder=TextEmbedder(model="sentence-transformers"),
    vector_store=vector_store
)

# Embed documents and store in one step
ids = manager.embed_and_store(documents, metadata=metadata_list)

# Search by semantic similarity
results = manager.search("machine learning algorithms", top_k=10)
```

## Similarity Computation

```python
from semantica.embeddings import calculate_similarity

# Cosine similarity (most common)
score = calculate_similarity(embedding_a, embedding_b, method="cosine")
# → 0.0 to 1.0

# Euclidean distance (converted to similarity)
score = calculate_similarity(embedding_a, embedding_b, method="euclidean")
```

## GPU Acceleration

```python
# Use CUDA GPU for faster embedding generation
generator = EmbeddingGenerator(model="sentence-transformers", device="cuda")
# device options: "cpu" | "cuda" | "mps"
```

## Embedding Cache

The embedding cache is used by Distance Intelligence (v0.5.0) to avoid recomputing embeddings for large N×N distance matrix calculations:

```python
embedder = TextEmbedder(
    model="sentence-transformers",
    cache_dir=".embeddings_cache",
    cache_ttl=3600    # seconds before cache entries expire
)
```

## Convenience Functions

```python
from semantica.embeddings import (
    embed_text, generate_embeddings, calculate_similarity,
    pool_embeddings, check_available_providers
)

# Single text
emb = embed_text("Hello world", method="sentence_transformers")

# Batch
embs = generate_embeddings(texts, method="openai")

# Check which providers are installed
providers = check_available_providers()
# → {"sentence_transformers": True, "fastembed": True, "openai": False}
```

<CardGroup cols={2}>
  <Card title="Vector Store" icon="database" href="vector_store">
    Store and search the generated embeddings.
  </Card>
  <Card title="Split" icon="scissors" href="split">
    Chunk text before embedding for better retrieval quality.
  </Card>
  <Card title="KG Module" icon="diagram-project" href="kg">
    Distance Intelligence uses graph embeddings.
  </Card>
  <Card title="Deduplication" icon="copy" href="deduplication">
    Semantic deduplication uses embeddings for entity resolution.
  </Card>
</CardGroup>
