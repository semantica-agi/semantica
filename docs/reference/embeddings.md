---
title: "Embeddings Module"
description: "Text and graph embedding generation — Sentence-Transformers, FastEmbed, OpenAI, BGE, Ollama — with pooling strategies, caching, and GPU acceleration."
icon: "vector-square"
---

`semantica.embeddings` converts text and graph structures into dense vectors. These vectors power semantic search, entity resolution, GraphRAG retrieval, and Distance Intelligence across every Semantica module. A single provider-agnostic API abstracts Sentence-Transformers, FastEmbed, OpenAI, BGE, and Ollama behind one interface.

## Why Embeddings Matter

Raw text can't be compared mathematically. Embeddings translate meaning into geometry — two semantically similar sentences produce vectors that are close together in high-dimensional space, even when they share no words.

Semantica uses embeddings for:

- **Semantic search** — find knowledge graph nodes by meaning, not just keywords
- **Entity resolution** — detect that "Apple Inc." and "Apple Computer" refer to the same entity
- **Deduplication** — `semantic_v2` strategy measures entity similarity via embedding distance
- **GraphRAG retrieval** — hybrid vector + graph traversal for grounded LLM answers
- **Distance Intelligence** — N×N semantic distance matrices across entity sets
- **Semantic chunking** — detect topic shift boundaries in `TextSplitter(method="semantic_transformer")`

## Exported Classes

```python
from semantica.embeddings import (
    # Core generators
    EmbeddingGenerator,      # main handler: generate_embeddings(text, data_type="text")
    TextEmbedder,            # text embedding: embed(text), embed_batch(texts)
    GraphEmbeddingManager,   # embed KG nodes/subgraphs for GraphRAG
    VectorEmbeddingManager,  # embedding management for vector databases
    # Provider stores
    OpenAIStore,             # OpenAI text-embedding-* API
    BGEStore,                # BAAI/bge-* via sentence-transformers
    FastEmbedStore,          # ONNX-accelerated, no CUDA required
    LlamaStore,              # Ollama local embedding models
    ProviderStoreFactory,    # create(provider="bge", model="...") factory
    # Pooling strategies
    MeanPooling,             # default — best for retrieval and clustering
    MaxPooling,              # captures presence of any feature
    CLSPooling,              # CLS token (BERT-style classification models)
    AttentionPooling,        # softmax-weighted sum
    HierarchicalPooling,     # for long documents exceeding context length
    PoolingStrategyFactory,  # create(strategy="mean") factory
    # Convenience functions
    embed_text,              # embed_text(text, method="sentence_transformers")
    generate_embeddings,     # generate_embeddings(texts, method="openai")
    calculate_similarity,    # calculate_similarity(a, b, method="cosine")
    pool_embeddings,         # pool_embeddings(token_embeddings, strategy="mean")
    check_available_providers, # returns {"sentence_transformers": True, ...}
)
```

## What You Get

<CardGroup cols={2}>
  <Card title="EmbeddingGenerator" icon="vector-square">
    Main entry point — provider-agnostic, handles batching automatically across all backends.
  </Card>
  <Card title="TextEmbedder" icon="text-size">
    Text-specific with automatic batching, disk caching, and progress tracking.
  </Card>
  <Card title="GraphEmbeddingManager" icon="diagram-project">
    Node and subgraph embeddings for structural similarity and GraphRAG context assembly.
  </Card>
  <Card title="VectorEmbeddingManager" icon="database">
    Full lifecycle: embed → store → search in a single coordinated workflow.
  </Card>
  <Card title="Provider Stores" icon="plug">
    `OpenAIStore`, `BGEStore`, `FastEmbedStore`, `LlamaStore`, and `ProviderStoreFactory`.
  </Card>
  <Card title="Pooling Strategies" icon="layer-group">
    Mean, Max, CLS, Attention, and Hierarchical — control token-to-vector aggregation.
  </Card>
</CardGroup>

## Installation

| Provider | Install Command | API Key Required |
| -------- | --------------- | ---------------- |
| Sentence-Transformers (default) | `pip install semantica` | No |
| FastEmbed | `pip install "semantica[fastembed]"` | No |
| BGE | `pip install semantica` | No (uses sentence-transformers) |
| OpenAI | `pip install "semantica[llm-openai]"` | Yes — `OPENAI_API_KEY` |
| Ollama (LlamaStore) | `pip install "semantica[llm-ollama]"` | No — local server |
| All providers | `pip install "semantica[all]"` | Varies |

Check which providers are available in your environment:

```python
from semantica.embeddings import check_available_providers

providers = check_available_providers()
# → {"sentence_transformers": True, "fastembed": True, "openai": False, "ollama": True}
```

## Quick Start

<Steps>
  <Step title="Install and initialize a provider">
    ```python
    from semantica.embeddings import EmbeddingGenerator

    # Default — Sentence-Transformers, free, runs locally
    generator = EmbeddingGenerator()

    # Custom model via config dict
    generator = EmbeddingGenerator(config={"text": {"method": "sentence_transformers", "model_name": "BAAI/bge-large-en-v1.5"}})
    ```
  </Step>
  <Step title="Generate embeddings">
    ```python
    embeddings = generator.generate_embeddings(["Text about AI", "Machine learning concepts"])
    ```
  </Step>
  <Step title="Compute similarity">
    ```python
    # Cosine similarity — 0.0 (unrelated) to 1.0 (identical meaning)
    score = generator.compare_embeddings(embeddings[0], embeddings[1], method="cosine")
    print(f"Similarity: {score:.3f}")
    ```
  </Step>
  <Step title="Embed and store for search">
    ```python
    from semantica.embeddings import VectorEmbeddingManager, TextEmbedder
    from semantica.vector_store import VectorStore

    vector_store = VectorStore(backend="faiss", dimension=384)
    manager = VectorEmbeddingManager(
        embedder=TextEmbedder(model="sentence-transformers"),
        vector_store=vector_store,
    )
    ids = manager.embed_and_store(documents, metadata=metadata_list)

    results = manager.search("machine learning algorithms", top_k=10)
    for result in results:
        print(f"Score: {result.score:.3f}  —  {result.metadata['title']}")
    ```
  </Step>
</Steps>

## Supported Models

| Provider | Model | Dimension | Speed | Best For |
| -------- | ----- | --------- | ----- | -------- |
| `sentence-transformers` | `all-MiniLM-L6-v2` | 384 | Fast | Default — good balance of speed and quality |
| `sentence-transformers` | `all-mpnet-base-v2` | 768 | Medium | Higher retrieval quality |
| `bge` | `BAAI/bge-large-en-v1.5` | 1024 | Medium | State-of-the-art retrieval accuracy |
| `bge` | `BAAI/bge-small-en-v1.5` | 384 | Fast | Lightweight, competitive quality |
| `fastembed` | `BAAI/bge-small-en-v1.5` | 384 | Very fast | CPU-optimised, low-latency production |
| `openai` | `text-embedding-3-small` | 1536 | API | Cost-effective OpenAI embedding |
| `openai` | `text-embedding-3-large` | 3072 | API | Highest quality via OpenAI API |
| `llama` (Ollama) | Any Ollama model | Varies | Local | Fully local, no API key |

## EmbeddingGenerator

<Tabs>
  <Tab title="Sentence-Transformers (default)">
    ```python
    from semantica.embeddings import EmbeddingGenerator

    # Default — Sentence-Transformers with all-MiniLM-L6-v2
    generator = EmbeddingGenerator()

    # Custom model via set_text_model
    generator.set_text_model("sentence_transformers", "BAAI/bge-large-en-v1.5")

    embeddings = generator.generate_embeddings(texts)
    similarity = generator.compare_embeddings(embeddings[0], embeddings[1])
    ```

    Best for: default prototyping, no API key, good quality.
  </Tab>
  <Tab title="FastEmbed">
    ```python
    from semantica.embeddings import EmbeddingGenerator

    generator = EmbeddingGenerator()
    generator.set_text_model("fastembed", "BAAI/bge-small-en-v1.5")
    embeddings = generator.generate_embeddings(texts)
    ```

    Best for: CPU-only production, lowest latency without GPU.
  </Tab>
  <Tab title="OpenAI">
    ```python
    from semantica.embeddings import OpenAIStore
    import os

    store     = OpenAIStore(api_key=os.getenv("OPENAI_API_KEY"), model="text-embedding-3-small")
    embedding = store.embed("Hello world")
    ```

    Best for: highest quality (3-large), or matching an OpenAI LLM pipeline.
  </Tab>
  <Tab title="Ollama (local)">
    ```python
    from semantica.embeddings import LlamaStore

    store     = LlamaStore(model="llama3.2", base_url="http://localhost:11434")
    embedding = store.embed("Hello world")
    ```

    Best for: air-gapped or privacy-sensitive environments — no data leaves your machine.
  </Tab>
  <Tab title="GPU acceleration">
    ```python
    from semantica.embeddings import EmbeddingGenerator

    # Set device via text embedder config
    generator = EmbeddingGenerator(config={"text": {"device": "cuda"}})

    # Apple Silicon (M1/M2/M3)
    generator = EmbeddingGenerator(config={"text": {"device": "mps"}})
    ```

    GPU reduces embedding time by 5–20× depending on batch size and model.
  </Tab>
</Tabs>

### Constructor Parameters

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `config` | `dict` | `None` | Config dict; `config["text"]` is passed to `TextEmbedder` |
| `**kwargs` | | | Additional key/value config merged into `config` |

Use `generator.set_text_model(method, model_name)` to switch the embedding model after construction.

## TextEmbedder

Specialised for text workloads — adds automatic batching, progress tracking, and disk caching:

```python
from semantica.embeddings import TextEmbedder

embedder = TextEmbedder(
    model="sentence-transformers",
    cache_dir=".emb_cache",   # persist embeddings to disk
    cache_ttl=86400,          # cache expiry in seconds (24h); None = never expires
    batch_size=128,
    show_progress=True,
)

# Single text
embedding = embedder.embed("A knowledge graph connects entities with typed relationships.")

# Batch — auto-splits into batch_size chunks, shows progress bar
embeddings = embedder.embed_batch(texts, show_progress=True)
```

**Key behaviours:**
- Cache is keyed on text content + model name — identical texts return cached vectors instantly
- Progress bar uses `tqdm` in terminal; switches to `tqdm.notebook` in Jupyter automatically
- Large batches (> 10k texts) are chunked internally to avoid OOM on GPU

## Provider Stores

Use provider stores directly when you need fine-grained control over a single backend:

```python
from semantica.embeddings import (
    OpenAIStore, BGEStore, FastEmbedStore, LlamaStore,
    ProviderStoreFactory,
)
import os

# OpenAI
store     = OpenAIStore(api_key=os.getenv("OPENAI_API_KEY"), model="text-embedding-3-small")
embedding = store.embed("Hello world")

# BGE (Sentence-Transformers wrapper)
store     = BGEStore(model="BAAI/bge-large-en-v1.5", device="cpu")
embedding = store.embed("Hello world")

# FastEmbed — ONNX runtime, no CUDA required
store     = FastEmbedStore(model="BAAI/bge-small-en-v1.5")
embedding = store.embed("Hello world")

# Ollama — fully local
store     = LlamaStore(model="llama3.2", base_url="http://localhost:11434")
embedding = store.embed("Hello world")

# Auto-select from a name string — useful in config-driven pipelines
store = ProviderStoreFactory.create(provider="bge", model="BAAI/bge-large-en-v1.5")
```

## Pooling Strategies

Transformer models produce one embedding per token. Pooling aggregates token embeddings into a single vector:

<Tabs>
  <Tab title="MeanPooling (default)">
    ```python
    from semantica.embeddings import MeanPooling

    pooler = MeanPooling()
    pooled = pooler.pool(token_embeddings)   # shape: (hidden_dim,)
    ```

    Best for: retrieval, semantic search, and clustering — averages all token contributions.
  </Tab>
  <Tab title="MaxPooling">
    ```python
    from semantica.embeddings import MaxPooling

    pooler = MaxPooling()
    pooled = pooler.pool(token_embeddings)
    ```

    Best for: capturing the presence of any feature — takes the max activation per dimension.
  </Tab>
  <Tab title="CLSPooling">
    ```python
    from semantica.embeddings import CLSPooling

    pooler = CLSPooling()
    pooled = pooler.pool(token_embeddings)
    ```

    Best for: classification-style tasks; models explicitly trained with CLS pooling (BERT).
  </Tab>
  <Tab title="HierarchicalPooling">
    ```python
    from semantica.embeddings import HierarchicalPooling

    # Chunk text, mean-pool within chunks, then mean-pool chunks
    pooler = HierarchicalPooling(chunk_size=512)
    pooled = pooler.pool(token_embeddings)
    ```

    Best for: long documents exceeding the model's max sequence length — reports, papers, contracts.
  </Tab>
  <Tab title="Strategy Comparison">

    | Strategy | When to Use |
    | -------- | ----------- |
    | `mean` | Default for retrieval, semantic search, and clustering |
    | `max` | When you want to capture the presence of any feature, not average presence |
    | `cls` | Classification-style tasks; models explicitly trained with CLS pooling (BERT) |
    | `attention` | When token importance varies significantly; slower but more accurate |
    | `hierarchical` | Long documents exceeding model context length; reports, papers, contracts |

    ```python
    from semantica.embeddings import PoolingStrategyFactory

    pooler = PoolingStrategyFactory.create(strategy="mean")
    ```

  </Tab>
</Tabs>

## GraphEmbeddingManager

Embed graph nodes and subgraphs for structural similarity and GraphRAG context assembly:

```python
from semantica.embeddings import GraphEmbeddingManager, TextEmbedder

manager = GraphEmbeddingManager(
    text_embedder=TextEmbedder(model="sentence-transformers"),
    graph_store=graph_store,   # optional — for persistence
)

# Embed all nodes — uses node label + property text
node_embeddings = manager.embed_nodes(kg)

# Embed a subgraph centred on a node (for GraphRAG context)
subgraph_embedding = manager.embed_subgraph(
    kg,
    center_node="Apple Inc.",
    hops=2,   # include neighbours up to 2 hops away
)

# Find semantically similar nodes by ID
similar = manager.find_similar_nodes("apple_inc", top_k=5)
for node_id, score in similar:
    print(f"{node_id}: {score:.3f}")
```

**Key behaviours:**
- Node embedding combines the label, type, and all property values into a single text string before embedding
- `hops=2` captures the local neighbourhood — increase for richer context, decrease for speed
- Results from `find_similar_nodes` are sorted by cosine similarity descending

## Embedding Cache

The disk cache avoids recomputing embeddings for unchanged text — critical for large corpora and repeated pipeline runs:

```python
from semantica.embeddings import TextEmbedder

embedder = TextEmbedder(
    model="sentence-transformers",
    cache_dir=".embeddings_cache",
    cache_ttl=3600,   # seconds — None means cache never expires
)

# First call: computes and caches
embeddings = embedder.embed_batch(texts)

# Second call (same texts): returns from cache instantly
embeddings = embedder.embed_batch(texts)
```

<Note>
  The Distance Intelligence module (v0.5.0) uses the same cache to avoid recomputing embeddings during N×N matrix calculations across large entity sets.
</Note>

## Similarity Computation

```python
from semantica.embeddings import calculate_similarity

# Cosine similarity — direction only, not magnitude; most common for text
score = calculate_similarity(embedding_a, embedding_b, method="cosine")
# → 0.0 (orthogonal / unrelated) to 1.0 (identical direction)

# Euclidean distance converted to similarity
score = calculate_similarity(embedding_a, embedding_b, method="euclidean")

# Dot product — use when vectors are already normalised (equivalent to cosine)
score = calculate_similarity(embedding_a, embedding_b, method="dot")
```

## Convenience Functions

```python
from semantica.embeddings import (
    embed_text, generate_embeddings, calculate_similarity,
    pool_embeddings, check_available_providers,
)

# Single text — fastest path
emb = embed_text("Hello world", method="sentence_transformers")

# Batch
embs = generate_embeddings(texts, method="openai")

# Check which providers are installed
providers = check_available_providers()
# → {"sentence_transformers": True, "fastembed": True, "openai": False}
```

## Tips and Common Pitfalls

<Warning>
  **Dimension mismatch.** The dimension you pass to `VectorStore(dimension=...)` must exactly match your embedding model's output. `all-MiniLM-L6-v2` → 384, `all-mpnet-base-v2` → 768, `bge-large-en-v1.5` → 1024. Check with `generator.dimension` before creating the store.
</Warning>

<Warning>
  **Not normalising for cosine similarity.** If you compute cosine similarity directly (dot product), vectors must be L2-normalised first. `EmbeddingGenerator` normalises by default (`normalize=True`). If you disable it, use `calculate_similarity(..., method="cosine")` which normalises internally.
</Warning>

<Warning>
  **Sequence length limits.** Most models have a 512-token limit. Text beyond that is silently truncated. Use `TextSplitter(method="hierarchical")` + `HierarchicalPooling` for long documents.
</Warning>

<Tip>
  **Always use the same model for indexing and querying.** Vectors from different models are not comparable — they live in different vector spaces. Switching models requires re-embedding your entire corpus.
</Tip>

<Tip>
  **Cache invalidation.** The cache key is the text + model name. Switching models requires clearing the cache or using a different `cache_dir` — otherwise you'll get stale vectors silently returned.
</Tip>

<CardGroup cols={2}>
  <Card title="Vector Store" icon="database" href="vector_store">
    Store and search the generated embeddings.
  </Card>
  <Card title="Split" icon="scissors" href="split">
    Chunk text before embedding for better retrieval quality.
  </Card>
  <Card title="KG Module" icon="diagram-project" href="kg">
    Distance Intelligence uses graph embeddings for semantic neighbourhoods.
  </Card>
  <Card title="Deduplication" icon="copy" href="deduplication">
    Semantic deduplication uses embedding distance for entity resolution.
  </Card>
</CardGroup>
