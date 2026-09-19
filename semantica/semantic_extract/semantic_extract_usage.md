# Semantic Extract Module Usage Guide

This comprehensive guide demonstrates how to use the semantic extraction module for extracting entities, relations, events, triplets, and semantic networks from text. The module provides multiple extraction methods including pattern-based, ML-based, and LLM-based approaches, with support for custom method registration and configuration management.

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Entity Extraction](#entity-extraction)
3. [Relation Extraction](#relation-extraction)
4. [Triplet Extraction](#triplet-extraction)
5. [Event Detection](#event-detection)
6. [Coreference Resolution](#coreference-resolution)
7. [Semantic Analysis](#semantic-analysis)
8. [Semantic Networks](#semantic-networks)
9. [Using Registry](#using-registry)
10. [Configuration](#configuration)
11. [Advanced Examples](#advanced-examples)

## Basic Usage

```python
from semantica.semantic_extract import NamedEntityRecognizer, RelationExtractor

text = "Apple Inc. was founded by Steve Jobs in 1976. The company is headquartered in Cupertino, California."

# Extract entities
ner = NamedEntityRecognizer()
entities = ner.extract_entities(text)
print(f"Entities: {entities}")

# Extract relations
rel_extractor = RelationExtractor()
relations = rel_extractor.extract(text, entities=entities)
print(f"Relations: {relations}")

print(f"Extracted {len(entities)} entities and {len(relations)} relations")
```

## Batch Processing & Provenance

All extractors support batch processing for high-throughput extraction. You can pass a list of strings or a list of dictionaries (with `content` and `id` keys).

**Features:**
- **Parallel Processing**: Multi-threaded extraction for high throughput (control via `max_workers`).
- **Progress Tracking**: Automatically shows a progress bar for large batches.
- **Provenance Metadata**: Each extracted item includes `batch_index` and `document_id` in its `metadata`.

```python
from semantica.semantic_extract import NERExtractor

documents = [
    {"id": "doc_1", "content": "Apple Inc. was founded by Steve Jobs."},
    {"id": "doc_2", "content": "Microsoft Corporation was founded by Bill Gates."}
]

# Initialize with parallel processing enabled
extractor = NERExtractor(max_workers=4)
batch_results = extractor.extract(documents)

# OR override during extraction call
# batch_results = extractor.extract(documents, max_workers=8)

for i, doc_entities in enumerate(batch_results):
    print(f"Document {i} entities:")
    for entity in doc_entities:
        print(f"  - {entity.text} ({entity.label})")
        print(f"    Provenance: Batch Index {entity.metadata['batch_index']}, Doc ID {entity.metadata.get('document_id')}")
```

## Robust Extraction Fallbacks

The framework implements robust fallback chains to prevent empty results when primary methods fail (e.g., due to model unavailability or obscure text).

- **NER**: `ML/LLM` -> `Pattern` -> `Last Resort` (Capitalized Words)
- **Relation**: `Primary` -> `Pattern` -> `Last Resort` (Adjacency)
- **Triplet**: `Primary` -> `Relation-to-Triplet` -> `Pattern`

This ensures that you almost always get *some* structured data, even if it requires falling back to simpler heuristics.

## Entity Extraction

### Basic Entity Extraction

```python
from semantica.semantic_extract import NamedEntityRecognizer

ner = NamedEntityRecognizer()
entities = ner.extract_entities("Apple Inc. was founded by Steve Jobs in 1976.")

for entity in entities:
    # metadata["confidence_source"] records where the score came from
    # (model/heuristic/...); confidence is None only for entities that
    # bypass the extraction pipeline without a backend score
    confidence = f"{entity.confidence:.2f}" if entity.confidence is not None else "N/A"
    print(f"{entity.text} ({entity.type}) - Confidence: {confidence}")
```

### Different Entity Extraction Methods

```python
from semantica.semantic_extract import NERExtractor

text = "Apple Inc. was founded by Steve Jobs in 1976."

# Pattern-based extraction
extractor = NERExtractor(method="pattern")
entities = extractor.extract(text)
print(f"Pattern method: {len(entities)} entities")

# Regex-based extraction
extractor = NERExtractor(method="regex")
entities = extractor.extract(text)
print(f"Regex method: {len(entities)} entities")

# ML-based extraction (spaCy)
extractor = NERExtractor(method="ml")
entities = extractor.extract(text)
print(f"ML method: {len(entities)} entities")

# HuggingFace model extraction (Bring Your Own Model)
extractor = NERExtractor(method="huggingface")

# Use a specific model and aggregation strategy at runtime
# Runtime options override configuration defaults
entities = extractor.extract(
    text, 
    model="dslim/bert-base-NER", 
    aggregation_strategy="max", # Options: "simple", "first", "average", "max"
    device="cpu" # or "cuda"
)
print(f"HuggingFace method: {len(entities)} entities")

# LLM-based extraction with advanced options
extractor = NERExtractor(method="llm")
entities = extractor.extract(
    text, 
    provider="openai", 
    model="gpt-4",
    silent_fail=False,      # Raise ProcessingError on failure (default)
    max_text_length=4000,   # Auto-chunking for long text (default: 64k for major providers)
    max_tokens=4096,        # Explicitly control generation output length
    temperature=0.0
)
print(f"LLM method: {len(entities)} entities")

# Groq extraction with long context support
# Groq defaults to 64k chunking limit for models like llama-3.3-70b
groq_extractor = NERExtractor(method="llm")
groq_entities = groq_extractor.extract(
    text,
    provider="groq",
    model="llama-3.3-70b-versatile",
    max_tokens=8000 # Passed directly to Groq API
)
print(f"Groq method: {len(groq_entities)} entities")
```

### Using NERExtractor Directly

```python
from semantica.semantic_extract import NERExtractor

# 1. Standard ML (spaCy)
extractor = NERExtractor(method="ml", model="en_core_web_trf")
entities = extractor.extract(text)

# 2. LLM-based extraction
extractor = NERExtractor(
    method="llm", 
    provider="openai", 
    model="gpt-4",
    temperature=0.0
)
entities = extractor.extract(text)

# 3. Regex with custom patterns
extractor = NERExtractor(
    method="regex", 
    patterns={"CODE": r"[A-Z]{3}-\d{3}"}
)
entities = extractor.extract(text)

for entity in entities:
    print(f"Entity: {entity.text}")
    print(f"  Type: {entity.label}")
    print(f"  Confidence: {entity.confidence}")
```

### Entity Classification and Confidence Scoring

```python
from semantica.semantic_extract import EntityClassifier, EntityConfidenceScorer
from semantica.semantic_extract.types import Entity

classifier = EntityClassifier()
scorer = EntityConfidenceScorer()

entity = Entity(text="Apple Inc.", label="ORG", start_char=0, end_char=10)

# Classify entity
classification = classifier.classify_entity_type(entity)
print(f"Classification: {classification}")

# Score confidence — score_entities() accepts a list and returns the same list
# with confidence filled in for any entity that had confidence=None
(scored,) = scorer.score_entities([entity])
confidence = scored.confidence
conf_str = f"{confidence:.2f}" if confidence is not None else "N/A"
print(f"Confidence: {conf_str}")
```

## Relation Extraction

### Basic Relation Extraction

```python
from semantica.semantic_extract import RelationExtractor

extractor = RelationExtractor()
text = "Steve Jobs founded Apple Inc. in 1976."

relations = extractor.extract(text, entities=entities)

for relation in relations:
    print(f"{relation.subject} --[{relation.predicate}]--> {relation.object}")
    print(f"  Confidence: {relation.confidence:.2f}")
```

### Different Relation Extraction Methods

```python
from semantica.semantic_extract import RelationExtractor

text = "Steve Jobs founded Apple Inc."

# Pattern-based extraction
extractor = RelationExtractor(method="pattern")
relations = extractor.extract(text, entities=entities)

# Dependency parsing-based
extractor = RelationExtractor(method="dependency")
relations = extractor.extract(text, entities=entities)

# Co-occurrence based
extractor = RelationExtractor(method="cooccurrence")
relations = extractor.extract(text, entities=entities)

# HuggingFace model (Bring Your Own Model)
extractor = RelationExtractor(method="huggingface")

# Use a sequence classification model trained for relations
# The extractor automatically formats input with entity markers: 
# "Steve Jobs founded Apple" -> "<subj> Steve Jobs </subj> founded <obj> Apple </obj>"
relations = extractor.extract(
    text, 
    entities=entities, 
    model="semantica/relation-model-v1", # Replace with your model ID
    device="cpu"
)

# LLM-based relation extraction
extractor = RelationExtractor(method="llm")
relations = extractor.extract(
    text, 
    entities=entities, 
    provider="openai",
    model="gpt-4",
    max_tokens=2048, # Increased output limit for many relations
    silent_fail=True  # Return empty list if extraction fails
)
```

### Relation Types

```python
from semantica.semantic_extract import Relation

# Create relation manually
relation = Relation(
    subject="Steve Jobs",
    predicate="founded",
    object="Apple Inc.",
    confidence=0.95,
    metadata={"source": "text", "position": 0}
)

print(f"Relation: {relation.subject} --[{relation.predicate}]--> {relation.object}")
```

## Triplet Extraction

### Basic Triplet Extraction

```python
from semantica.semantic_extract import TripletExtractor

extractor = TripletExtractor()
text = "Apple Inc. was founded by Steve Jobs in 1976."

triplets = extractor.extract_triplets(text)

for triplet in triplets:
    print(f"({triplet.subject}, {triplet.predicate}, {triplet.object})")
    print(f"  Confidence: {triplet.confidence:.2f}")
```

### Different Triplet Extraction Methods

```python
from semantica.semantic_extract import TripletExtractor

text = "Apple Inc. was founded by Steve Jobs in 1976."

# Pattern-based
extractor = TripletExtractor(method="pattern")
triplets = extractor.extract_triplets(text)

# Rules-based
extractor = TripletExtractor(method="rules")
triplets = extractor.extract_triplets(text)

# HuggingFace model (Seq2Seq / REBEL)
extractor = TripletExtractor(method="huggingface")

# Use a Seq2Seq model like REBEL for end-to-end triplet extraction
# This method generates triplets directly from text without needing separate NER/RE steps
triplets = extractor.extract_triplets(
    text, 
    model="Babelscape/rebel-large",
    device="cpu"
)

# LLM-based triplet extraction
extractor = TripletExtractor(method="llm")
triplets = extractor.extract_triplets(
    text, 
    provider="openai", 
    model="gpt-4",
    max_text_length=64000, # Large default chunk size supported
    max_tokens=4096 # Ensure enough tokens for all triplets
)
```

### RDF Serialization

```python
from semantica.semantic_extract import TripletExtractor, RDFSerializer

extractor = TripletExtractor()
triplets = extractor.extract_triplets(text)

# Serialize to RDF
serializer = RDFSerializer()
rdf_output = serializer.serialize(triplets, format="turtle")
print(rdf_output)

# Serialize to JSON-LD
jsonld_output = serializer.serialize(triplets, format="json-ld")
print(jsonld_output)
```

### Triplet Validation

```python
from semantica.semantic_extract import TripletValidator, TripletQualityChecker

validator = TripletValidator()
quality_checker = TripletQualityChecker()

for triplet in triplets:
    # Validate triplet
    is_valid = validator.validate(triplet)
    print(f"Valid: {is_valid}")
    
    # Check quality
    quality = quality_checker.check_quality(triplet)
    print(f"Quality score: {quality:.2f}")
```

## Event Detection

### Basic Event Detection

```python
from semantica.semantic_extract import EventDetector

detector = EventDetector()
text = "Apple Inc. was founded in 1976. The company launched the iPhone in 2007."

events = detector.detect_events(text)

for event in events:
    print(f"Event: {event.text}")
    print(f"  Type: {event.type}")
    print(f"  Trigger: {event.trigger}")
    print(f"  Participants: {event.participants}")
    print(f"  Temporal: {event.temporal}")
```

### Event Classification

```python
from semantica.semantic_extract import EventClassifier

classifier = EventClassifier()
event = {"text": "Apple Inc. was founded", "trigger": "founded"}

event_type = classifier.classify(event)
print(f"Event type: {event_type}")
```

### Temporal Event Processing

```python
from semantica.semantic_extract import TemporalEventProcessor

processor = TemporalEventProcessor()
events = detector.detect_events(text)

# Process temporal information
processed_events = processor.process(events)

for event in processed_events:
    print(f"Event: {event.text}")
    print(f"  Time: {event.temporal.get('time')}")
    print(f"  Duration: {event.temporal.get('duration')}")
```

## Coreference Resolution

### Basic Coreference Resolution

```python
from semantica.semantic_extract import CoreferenceResolver

resolver = CoreferenceResolver()
text = "Apple Inc. was founded in 1976. The company is headquartered in Cupertino."

coreferences = resolver.resolve(text)

for chain in coreferences:
    print(f"Coreference chain: {chain.mentions}")
    print(f"  Representative: {chain.representative}")
```

### Pronoun Resolution

```python
from semantica.semantic_extract import PronounResolver

pronoun_resolver = PronounResolver()
text = "Steve Jobs founded Apple. He was the CEO."

resolved = pronoun_resolver.resolve(text)
print(f"Resolved text: {resolved}")
```

### Entity Coreference Detection

```python
from semantica.semantic_extract import EntityCoreferenceDetector

detector = EntityCoreferenceDetector()
entities = [
    {"text": "Apple Inc.", "type": "ORG"},
    {"text": "Apple", "type": "ORG"},
    {"text": "the company", "type": "ORG"}
]

coreferences = detector.detect(entities)
print(f"Found {len(coreferences)} coreference chains")
```

## Semantic Analysis

### Basic Semantic Analysis

```python
from semantica.semantic_extract import SemanticAnalyzer

analyzer = SemanticAnalyzer()
text = "Apple Inc. was founded by Steve Jobs in 1976."

analysis = analyzer.analyze(text)

print(f"Semantic roles: {analysis.roles}")
print(f"Clusters: {analysis.clusters}")
```

### Semantic Role Labeling

```python
from semantica.semantic_extract import RoleLabeler

labeler = RoleLabeler()
text = "Steve Jobs founded Apple Inc."

roles = labeler.label(text)

for role in roles:
    print(f"Role: {role.role}")
    print(f"  Argument: {role.argument}")
    print(f"  Type: {role.type}")
```

### Semantic Clustering

```python
from semantica.semantic_extract import SemanticClusterer

clusterer = SemanticClusterer()
entities = [
    {"text": "Apple Inc.", "type": "ORG"},
    {"text": "Microsoft", "type": "ORG"},
    {"text": "Google", "type": "ORG"}
]

clusters = clusterer.cluster(entities)

for cluster in clusters:
    print(f"Cluster: {cluster.label}")
    print(f"  Entities: {[e['text'] for e in cluster.entities]}")
```

### Similarity Analysis

```python
from semantica.semantic_extract import SimilarityAnalyzer

similarity_analyzer = SimilarityAnalyzer()
entity1 = {"text": "Apple Inc.", "type": "ORG"}
entity2 = {"text": "Apple", "type": "ORG"}

similarity = similarity_analyzer.analyze(entity1, entity2)
print(f"Similarity: {similarity:.2f}")
```

## Semantic Networks

### Building Semantic Networks

```python
from semantica.semantic_extract import SemanticNetworkExtractor

extractor = SemanticNetworkExtractor()
text = "Apple Inc. was founded by Steve Jobs in 1976. The company is headquartered in Cupertino."

network = extractor.extract(text)

print(f"Nodes: {len(network.nodes)}")
print(f"Edges: {len(network.edges)}")

for node in network.nodes:
    print(f"Node: {node.label} ({node.type})")

for edge in network.edges:
    print(f"Edge: {edge.source} --[{edge.relation}]--> {edge.target}")
```

### Semantic Network Components

```python
from semantica.semantic_extract import SemanticNode, SemanticEdge

# Create semantic node
node = SemanticNode(
    label="Apple Inc.",
    type="ORG",
    properties={"founded": 1976}
)

# Create semantic edge
edge = SemanticEdge(
    source="Steve Jobs",
    target="Apple Inc.",
    relation="founded",
    weight=0.95
)

print(f"Node: {node.label}")
print(f"Edge: {edge.source} --[{edge.relation}]--> {edge.target}")
```


## Using Registry

### Registering Custom Methods

```python
from semantica.semantic_extract.registry import method_registry

# Custom entity extraction method
def custom_entity_extraction(text, **kwargs):
    # Your custom extraction logic
    entities = []
    # ... extraction code ...
    return entities

# Register custom method
method_registry.register("entity", "custom_method", custom_entity_extraction)

# Use custom method
from semantica.semantic_extract import NERExtractor
extractor = NERExtractor(method="custom_method")
```

## Result Caching

Extraction results are cached (keyed by a stable SHA-256 over the input text and
generation parameters — `provider`, `model`, `temperature`, `seed`, ... — with
sensitive keys such as `api_key` excluded). The default cache is in-memory
(LRU + TTL) and lives only for the process.

### Persistent cache (sqlite)

An optional persistent backend keeps results across process restarts, so a
fresh process (CI job, notebook kernel, batch worker) reuses prior results
instead of re-paying the LLM. Select it via config, environment, or at runtime:

```python
from semantica.semantic_extract import configure_cache

# Runtime (rebuilds the global cache in place):
configure_cache(backend="sqlite", path="~/.cache/semantica/extract.sqlite3")
```

```bash
# Environment (applied at import time):
export SEMANTICA_CACHE_BACKEND=sqlite
export SEMANTICA_CACHE_PATH=~/.cache/semantica/extract.sqlite3
# also: SEMANTICA_CACHE_TTL, SEMANTICA_CACHE_SIZE, SEMANTICA_CACHE_ENABLED
```

If the persistent backend cannot be constructed, it degrades gracefully to the
in-memory default — extraction never fails because of a cache misconfiguration.

### ⚠️ Persistent cache trust model

The sqlite file is deserialized back into the process on every read, and the
**default serializer is `pickle`**. Treat the cache file as executable input:

- `cache_path` / `SEMANTICA_CACHE_PATH` **must** point at a **trusted,
  user-private** location. The default (`$XDG_CACHE_HOME` or `~/.cache`,
  created `0o700`; the db file created `0o600`) satisfies this.
- The cache may contain **sensitive extraction results** in the clear.
- The default `pickle` serializer must only be used with a trusted cache file.
  For untrusted or shared locations, pass a non-executable serializer
  (e.g. `json`) when constructing `SqliteCacheBackend`.

For safety the backend creates the file atomically with `0o600` and refuses an
existing path that is a symlink, a non-regular file, or owned by another user
(falling back to the in-memory cache).

Cache-key invalidation is automatic: because provider/model/generation
parameters are part of the key, changing any of them (e.g. a model upgrade)
produces a different key and old entries are bypassed rather than served stale.
