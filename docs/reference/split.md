---
title: "Split Module"
description: "15+ text chunking methods including recursive, semantic, entity-aware, and relation-aware splitting."
icon: "scissors"
---

`semantica.split` breaks documents into chunks while preserving semantic context — critical for embedding quality in RAG systems and accurate entity extraction in NER pipelines.

## What You Get

- **`TextSplitter`** — unified interface for 9+ chunking strategies
- **Entity-aware chunking** — entity mentions never split across chunk boundaries
- **Relation-aware chunking** — subject–predicate–object triplets kept intact
- **Semantic chunking** — split at topic shift boundaries using embedding similarity
- **`Chunk`** — output object with text, token count, character offsets, and metadata

## TextSplitter

```python
from semantica.split import TextSplitter

splitter = TextSplitter(
    method="semantic_transformer",   # see methods table below
    chunk_size=1000,                 # target tokens per chunk
    chunk_overlap=200                # token overlap between adjacent chunks
)

chunks = splitter.split(text)
for chunk in chunks:
    print(f"Chunk {chunk.metadata['chunk_index']}: {chunk.text[:80]}...")
    print(f"  Tokens: {chunk.token_count}")
```

## Splitting Methods

| Method | Description | Best For |
| ------ | ----------- | -------- |
| `recursive` | Split by paragraph → sentence → word (cascading) | General purpose |
| `semantic_transformer` | Split at semantic topic boundaries via sentence transformer | RAG retrieval |
| `entity_aware` | Keep entity mentions intact across boundaries | NER pipelines |
| `relation_aware` | Keep relation triplets intact | KG construction |
| `sentence` | Split by sentence boundary | Short content |
| `token` | Split by token count (tiktoken) | LLM context windows |
| `fixed` | Fixed character count with overlap | Batch processing |
| `markdown` | Split by Markdown heading hierarchy | Documentation |
| `code` | Split by function/class/method boundaries | Code analysis |

## Entity-Aware Chunking

Entity mentions are never split across chunk boundaries, preserving context for downstream NER:

```python
from semantica.split import TextSplitter
from semantica.semantic_extract import NERExtractor

ner = NERExtractor()
entities = ner.extract(text)

splitter = TextSplitter(method="entity_aware")
chunks = splitter.split(text, entities=entities)
# → Each chunk contains only complete entity mentions
```

## Relation-Aware Chunking

Subject–predicate–object triplets are kept within the same chunk:

```python
from semantica.split import TextSplitter

splitter = TextSplitter(method="relation_aware")
chunks = splitter.split(text, relationships=relationships)
# → Triplets are never split across chunk boundaries
```

## Semantic Chunking

Split at topic shift boundaries detected via embedding similarity:

```python
from semantica.split import TextSplitter
from semantica.embeddings import EmbeddingGenerator

embedder = EmbeddingGenerator(model="sentence-transformers")
splitter = TextSplitter(
    method="semantic_transformer",
    embedder=embedder,
    similarity_threshold=0.7   # split when consecutive sentence similarity drops below this
)

chunks = splitter.split(text)
```

## Token-Based Chunking

Use tiktoken for precise token-count control when preparing LLM context windows:

```python
splitter = TextSplitter(
    method="token",
    chunk_size=512,              # max tokens per chunk
    chunk_overlap=50,            # overlap in tokens
    tokenizer="cl100k_base"      # OpenAI tokenizer
)
chunks = splitter.split(text)
```

## Chunk Object

```python
@dataclass
class Chunk:
    text:        str        # chunk text content
    start_char:  int        # character offset in source document
    end_char:    int        # character offset in source document
    token_count: int        # number of tokens
    metadata:    Dict       # source_id, chunk_index, section_title, page_number, etc.
    entities:    List[Dict] # entities in chunk (entity_aware splitting only)
```

## Pipeline Integration

```python
from semantica.pipeline import Pipeline
from semantica.split import TextSplitter

pipeline = Pipeline()
pipeline.add_step("split", TextSplitter(method="semantic_transformer", chunk_size=512))
result = pipeline.run(documents)
```

<CardGroup cols={2}>
  <Card title="Parse" icon="file-lines" href="parse">
    Parse documents before chunking.
  </Card>
  <Card title="Embeddings" icon="vector-square" href="embeddings">
    Embed chunks for vector search and semantic chunking.
  </Card>
  <Card title="Semantic Extract" icon="magnifying-glass" href="semantic_extract">
    Extract entities from individual chunks.
  </Card>
  <Card title="Pipeline" icon="gear" href="pipeline">
    Integrate splitting as a pipeline step.
  </Card>
</CardGroup>
