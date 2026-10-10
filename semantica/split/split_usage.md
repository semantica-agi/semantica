# Split Module Usage Guide

This comprehensive guide demonstrates how to use the split module for text chunking and splitting using various methods. The module supports standard text splitting methods (recursive, token-based, sentence-based, etc.) as well as KG/ontology-aware methods (entity-aware, relation-aware, graph-based, etc.) for knowledge graph workflows.

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Standard Splitting Methods](#standard-splitting-methods)
3. [KG/Ontology-Aware Methods](#kgontology-aware-methods)
4. [Using Methods](#using-methods)
5. [Using Registry](#using-registry)
6. [Configuration](#configuration)
7. [Advanced Examples](#advanced-examples)

## Basic Usage

### Using TextSplitter

```python
from semantica.split import TextSplitter

text = """
This is a long document that needs to be split into chunks.
It contains multiple paragraphs and sentences.
We want to split it into manageable pieces for processing.
"""

# Recursive splitting (default)
splitter = TextSplitter(
    method="recursive",
    chunk_size=1000,
    chunk_overlap=200
)

chunks = splitter.split(text)
print(f"Split into {len(chunks)} chunks")

for i, chunk in enumerate(chunks):
    print(f"Chunk {i+1}: {len(chunk.text)} characters")
    print(f"  Text: {chunk.text[:50]}...")
```

### Using Convenience Functions

```python
from semantica.split.methods import split_recursive, split_by_tokens

text = "Your long text here..."

# Recursive splitting
chunks = split_recursive(text, chunk_size=1000, chunk_overlap=200)

# Token-based splitting
chunks = split_by_tokens(text, chunk_size=500, chunk_overlap=50)
```

## Standard Splitting Methods

### Recursive Splitting

```python
from semantica.split import TextSplitter

splitter = TextSplitter(
    method="recursive",
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""]
)

chunks = splitter.split(text)
```

### Token-based Splitting

```python
from semantica.split.methods import split_by_tokens

chunks = split_by_tokens(
    text,
    chunk_size=500,
    chunk_overlap=50,
    tokenizer="tiktoken",
    model="gpt-4"
)

for chunk in chunks:
    print(f"Tokens: {chunk.metadata.get('token_count')}")
```

### Sentence-based Splitting

```python
from semantica.split.methods import split_by_sentences

chunks = split_by_sentences(
    text,
    chunk_size=10,  # Number of sentences
    chunk_overlap=2
)

for chunk in chunks:
    print(f"Sentences: {chunk.metadata.get('sentence_count')}")
```

### Paragraph-based Splitting

```python
from semantica.split.methods import split_by_paragraphs

chunks = split_by_paragraphs(
    text,
    chunk_size=5,  # Number of paragraphs
    chunk_overlap=1
)
```

### Character-based Splitting

```python
from semantica.split.methods import split_by_characters

chunks = split_by_characters(
    text,
    chunk_size=1000,
    chunk_overlap=200
)
```

### Word-based Splitting

```python
from semantica.split.methods import split_by_words

chunks = split_by_words(
    text,
    chunk_size=500,  # Number of words
    chunk_overlap=50
)
```

### Semantic Transformer Splitting

```python
from semantica.split.methods import split_semantic_transformer

chunks = split_semantic_transformer(
    text,
    chunk_size=1000,
    chunk_overlap=200,
    model="sentence-transformers/all-MiniLM-L6-v2"
)

for chunk in chunks:
    print(f"Semantic similarity: {chunk.metadata.get('similarity_score')}")
```

### LLM-based Splitting

```python
from semantica.split.methods import split_llm

chunks = split_llm(
    text,
    chunk_size=1000,
    provider="openai",
    model="gpt-4"
)

for chunk in chunks:
    print(f"Optimal split point: {chunk.metadata.get('split_reason')}")
```

### HuggingFace Model Splitting

```python
from semantica.split.methods import get_split_method

hf_method = get_split_method("huggingface")
chunks = hf_method(
    text,
    chunk_size=1000,
    model="bert-base-uncased"
)
```

### NLTK-based Splitting

```python
from semantica.split import TextSplitter

splitter = TextSplitter(
    method="nltk",
    chunk_size=1000,
    chunk_overlap=200
)

chunks = splitter.split(text)
```

## KG/Ontology-Aware Methods

### Entity-Aware Splitting

```python
from semantica.split.methods import split_entity_aware

chunks = split_entity_aware(
    text,
    chunk_size=1000,
    chunk_overlap=200,
    ner_method="ml",  # "ml" (spaCy), "llm", or "pattern"
    preserve_entities=True
)

for chunk in chunks:
    print(f"Entities in chunk: {chunk.metadata.get('entities')}")
```

### Relation-Aware Splitting

```python
from semantica.split.methods import split_relation_aware

chunks = split_relation_aware(
    text,
    chunk_size=1000,
    chunk_overlap=200,
    preserve_triplets=True
)

for chunk in chunks:
    print(f"Triplets in chunk: {chunk.metadata.get('triplets')}")
```

### Graph-based Splitting

```python
from semantica.split.methods import split_graph_based

chunks = split_graph_based(
    text,
    chunk_size=1000,
    graph_structure="knowledge_graph"
)

for chunk in chunks:
    print(f"Graph nodes: {chunk.metadata.get('graph_nodes')}")
```

### Ontology-Aware Splitting

```python
from semantica.split.methods import split_ontology_aware

chunks = split_ontology_aware(
    text,
    chunk_size=1000,
    ontology="domain_ontology.owl"
)

for chunk in chunks:
    print(f"Concepts: {chunk.metadata.get('ontology_concepts')}")
```

### Hierarchical Splitting

```python
from semantica.split.methods import split_hierarchical

chunks = split_hierarchical(
    text,
    levels=["document", "section", "paragraph"],
    chunk_size=1000
)

for chunk in chunks:
    print(f"Level: {chunk.metadata.get('hierarchy_level')}")
```

### Using Existing Chunkers

```python
from semantica.split import (
    SemanticChunker,
    StructuralChunker,
    SlidingWindowChunker,
    TableChunker,
    EntityAwareChunker,
    RelationAwareChunker,
    GraphBasedChunker,
    OntologyAwareChunker,
    HierarchicalChunker
)

# Semantic chunking
semantic_chunker = SemanticChunker(
    chunk_size=1000,
    chunk_overlap=200
)
chunks = semantic_chunker.chunk(text)

# Structural chunking
structural_chunker = StructuralChunker()
chunks = structural_chunker.chunk(text)

# Sliding window chunking
sliding_chunker = SlidingWindowChunker(
    chunk_size=1000,
    overlap=200,  # max budget for repeated trailing sentences; actual overlap may be smaller or zero
)
chunks = sliding_chunker.chunk(text, preserve_boundaries=True)

# Table-specific chunking
table_chunker = TableChunker(
    preserve_headers=True,
    max_rows_per_chunk=50,
    include_context=True
)
chunks = table_chunker.chunk(text_with_tables)

# Entity-aware chunking
entity_chunker = EntityAwareChunker(
    chunk_size=1000,
    chunk_overlap=200,
    ner_method="ml",
    preserve_entities=True
)
chunks = entity_chunker.chunk(text)

# Relation-aware chunking
relation_chunker = RelationAwareChunker(
    chunk_size=1000,
    preserve_triplets=True
)
chunks = relation_chunker.chunk(text)

# Graph-based chunking
graph_chunker = GraphBasedChunker(
    chunk_size=1000,
    centrality_method="betweenness",
    community_algorithm="louvain"
)
chunks = graph_chunker.chunk(text, graph=knowledge_graph)

# Ontology-aware chunking
ontology_chunker = OntologyAwareChunker(
    chunk_size=1000,
    chunk_overlap=200,
    ontology_path="domain_ontology.owl",
    preserve_concepts=True
)
chunks = ontology_chunker.chunk(text)

# Hierarchical chunking
hierarchical_chunker = HierarchicalChunker(
    chunk_sizes=[2000, 1000, 500],
    chunk_overlaps=[400, 200, 100],
    create_parent_chunks=True
)
chunks = hierarchical_chunker.chunk(text)
```

## Using Methods

### Getting Available Methods

```python
from semantica.split.methods import get_split_method, list_available_methods

# List all available methods
all_methods = list_available_methods()
print("Available methods:", all_methods)

# Get specific method
recursive_method = get_split_method("recursive")
chunks = recursive_method(text, chunk_size=1000, chunk_overlap=200)
```

### Method Examples

```python
from semantica.split.methods import (
    split_recursive,
    split_by_tokens,
    split_by_sentences,
    split_by_paragraphs,
    split_by_characters,
    split_by_words,
    split_semantic_transformer,
    split_llm,
    split_entity_aware,
    split_relation_aware,
    split_graph_based,
    split_ontology_aware,
    split_hierarchical
)

# Standard methods
chunks1 = split_recursive(text, chunk_size=1000, chunk_overlap=200)
chunks2 = split_by_tokens(text, chunk_size=500, chunk_overlap=50)
chunks3 = split_by_sentences(text, chunk_size=10, chunk_overlap=2)
chunks4 = split_by_paragraphs(text, chunk_size=5, chunk_overlap=1)
chunks5 = split_by_characters(text, chunk_size=1000, chunk_overlap=200)
chunks6 = split_by_words(text, chunk_size=500, chunk_overlap=50)

# Advanced methods
chunks7 = split_semantic_transformer(text, chunk_size=1000, chunk_overlap=200)
chunks8 = split_llm(text, chunk_size=1000, provider="openai")
chunks9 = split_entity_aware(text, chunk_size=1000, ner_method="ml")
chunks10 = split_relation_aware(text, chunk_size=1000)
chunks11 = split_graph_based(text, chunk_size=1000)
chunks12 = split_ontology_aware(text, chunk_size=1000)
chunks13 = split_hierarchical(text, chunk_size=1000)
```

## Using Registry

### Registering Custom Methods

```python
from semantica.split.registry import method_registry

# Custom splitting method
def custom_split_method(text, chunk_size=1000, chunk_overlap=200, **kwargs):
    from semantica.split.semantic_chunker import Chunk
    
    # Your custom splitting logic
    chunks = []
    # ... splitting code ...
    
    return chunks

# Register custom method
method_registry.register("split", "custom_method", custom_split_method)

# Use custom method
from semantica.split.methods import get_split_method
custom_method = get_split_method("custom_method")
chunks = custom_method(text, chunk_size=1000)
```

### Listing Registered Methods

```python
from semantica.split.registry import method_registry

# List all registered methods
all_methods = method_registry.list_all()
print("Registered methods:", all_methods)

# List methods for split task
split_methods = method_registry.list_all("split")
print("Split methods:", split_methods)
```

## Configuration

### Using Configuration Manager

```python
from semantica.split.config import split_config

# Get configuration values
chunk_size = split_config.get("chunk_size", default=1000)
chunk_overlap = split_config.get("chunk_overlap", default=200)

# Set configuration values
split_config.set("chunk_size", 2000)
split_config.set("chunk_overlap", 400)

# Method-specific configuration
split_config.set_method_config("recursive", separators=["\n\n", "\n", ". "])
recursive_config = split_config.get_method_config("recursive")

# Get all configuration
all_config = split_config.get_all()
print("All config:", all_config)
```

### Environment Variables

```bash
# Set environment variables
export SPLIT_CHUNK_SIZE=1000
export SPLIT_CHUNK_OVERLAP=200
export SPLIT_DEFAULT_METHOD=recursive
```

### Configuration File

```yaml
# config.yaml
split:
  chunk_size: 1000
  chunk_overlap: 200
  default_method: recursive

split_methods:
  recursive:
    separators: ["\n\n", "\n", ". ", " "]
  semantic_transformer:
    model: "sentence-transformers/all-MiniLM-L6-v2"
```

```python
from semantica.split.config import SplitConfig

# Load from config file
config = SplitConfig(config_file="config.yaml")
chunk_size = config.get("chunk_size")
```

## Advanced Examples

### Chunk Validation

```python
from semantica.split import ChunkValidator

validator = ChunkValidator()

chunks = splitter.split(text)

# Validate chunks
for chunk in chunks:
    validation = validator.validate(chunk)
    print(f"Chunk valid: {validation.valid}")
    print(f"  Issues: {validation.issues}")
    print(f"  Quality score: {validation.quality_score:.2f}")
```

### Provenance Tracking

```python
from semantica.split import ProvenanceTracker

tracker = ProvenanceTracker()

chunks = splitter.split(text)

# Track chunk provenance
for chunk in chunks:
    provenance = tracker.track(chunk, source="document.pdf")
    print(f"Chunk provenance: {provenance}")
```

### Table-Specific Chunking

```python
from semantica.split import TableChunker

table_chunker = TableChunker()
text_with_tables = """
Document with tables...

| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |
"""

chunks = table_chunker.chunk(text_with_tables)

for chunk in chunks:
    if chunk.metadata.get("is_table"):
        print(f"Table chunk: {chunk.metadata.get('table_info')}")
```

### Multi-level Chunking

```python
from semantica.split import HierarchicalChunker

hierarchical_chunker = HierarchicalChunker(
    levels=["document", "section", "paragraph", "sentence"]
)

chunks = hierarchical_chunker.chunk(text)

for chunk in chunks:
    print(f"Level: {chunk.metadata.get('level')}")
    print(f"  Parent: {chunk.metadata.get('parent_id')}")
    print(f"  Children: {chunk.metadata.get('children_ids')}")
```

### Entity-Aware Chunking for GraphRAG

```python
from semantica.split import EntityAwareChunker

# Entity-aware chunking preserves entity boundaries
entity_chunker = EntityAwareChunker(
    chunk_size=1000,
    chunk_overlap=200,
    ner_method="llm",
    preserve_entities=True
)

chunks = entity_chunker.chunk(text)

for chunk in chunks:
    entities = chunk.metadata.get("entities", [])
    print(f"Chunk entities: {[e['text'] for e in entities]}")
    
    # Use for GraphRAG
    # Entities are preserved across chunk boundaries
```

### Relation-Aware Chunking for KG

```python
from semantica.split import RelationAwareChunker

# Relation-aware chunking preserves triplet integrity
relation_chunker = RelationAwareChunker(
    chunk_size=1000,
    preserve_triplets=True
)

chunks = relation_chunker.chunk(text)

for chunk in chunks:
    triplets = chunk.metadata.get("triplets", [])
    print(f"Chunk triplets: {len(triplets)}")
    
    # Use for knowledge graph construction
    # Triplets are preserved within chunks
```

### Semantic Chunking with Custom Model

```python
from semantica.split import SemanticChunker

semantic_chunker = SemanticChunker(
    chunk_size=1000,
    chunk_overlap=200,
    embedding_model="sentence-transformers/all-mpnet-base-v2",
    similarity_threshold=0.7
)

chunks = semantic_chunker.chunk(text)

for chunk in chunks:
    print(f"Semantic boundary: {chunk.metadata.get('is_semantic_boundary')}")
    print(f"Similarity: {chunk.metadata.get('similarity_score')}")
```

### Batch Processing

```python
from semantica.split import TextSplitter

splitter = TextSplitter(method="recursive", chunk_size=1000, chunk_overlap=200)

texts = [
    "First long document...",
    "Second long document...",
    "Third long document..."
]

# Process multiple texts
all_chunks = []
for text in texts:
    chunks = splitter.split(text)
    all_chunks.extend(chunks)

print(f"Total chunks: {len(all_chunks)}")
```

### Chunk Metadata and Filtering

```python
from semantica.split import TextSplitter

splitter = TextSplitter(method="recursive", chunk_size=1000, chunk_overlap=200)
chunks = splitter.split(text)

# Filter chunks by metadata
large_chunks = [
    chunk for chunk in chunks
    if chunk.metadata.get("token_count", 0) > 500
]

# Access chunk properties
for chunk in chunks:
    print(f"Text: {chunk.text[:50]}...")
    print(f"  Start: {chunk.start}")
    print(f"  End: {chunk.end}")
    print(f"  Metadata: {chunk.metadata}")
```

## Best Practices

1. **Choose appropriate method**: Use recursive for general text, entity-aware for GraphRAG, semantic for semantic boundaries
2. **Set appropriate chunk size**: Balance between context preservation and processing efficiency
3. **Use overlap**: Set chunk_overlap to preserve context across boundaries
4. **Validate chunks**: Always validate chunks for quality and completeness
5. **Track provenance**: Use provenance tracking for data lineage
6. **Entity-aware for KG**: Use entity-aware chunking when building knowledge graphs
7. **Semantic boundaries**: Use semantic chunking for better semantic coherence
8. **Customize separators**: Adjust separators based on your document structure

