---
title: "Semantic Extract Module"
description: "Named entity recognition, relation extraction, event detection, and triplet generation."
icon: "magnifying-glass-chart"
---

`semantica.semantic_extract` extracts structured information from unstructured text — the foundation of every knowledge graph in Semantica. All extractors support three modes: pattern-based (no API key), ML-based, and LLM-based.

## What You Get

- **`NERExtractor`** — named entity recognition: Person, Organization, Location, Date, and custom types
- **`RelationExtractor`** — typed semantic relationships between entities (`founded_by`, `located_in`, etc.)
- **`TripletExtractor`** — direct `(subject, predicate, object)` triplet generation for RDF-ready output
- **`EventExtractor`** — event detection with participants, temporal context, and confidence scores
- **`CoreferenceResolver`** — resolve "Apple" and "the company" to the same entity across a document

## NERExtractor

```python
from semantica.semantic_extract import NERExtractor
from semantica.llms import Groq
import os

# Pattern-based — fast, no API key, good for standard entity types
ner = NERExtractor(method="pattern")
entities = ner.extract("Apple Inc. was founded by Steve Jobs in Cupertino.")

# ML-based — higher accuracy, no API cost
ner = NERExtractor(method="ml", model="dslim/bert-large-NER")
entities = ner.extract(text)

# LLM-based — best accuracy, handles complex schemas and custom types
llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
ner = NERExtractor(method="llm", llm_provider=llm, max_retries=3)
entities = ner.extract(text)
```

Output format:

```python
[
    {"text": "Apple Inc.",  "type": "ORGANIZATION", "confidence": 0.98, "start": 0,  "end": 10},
    {"text": "Steve Jobs",  "type": "PERSON",       "confidence": 0.99, "start": 27, "end": 37},
    {"text": "Cupertino",   "type": "LOCATION",     "confidence": 0.97, "start": 41, "end": 50}
]
```

### Custom Entity Types

```python
ner = NERExtractor(
    method="pattern",
    custom_entities={
        "DRUG": ["aspirin", "ibuprofen", "metformin"],
        "GENE": ["BRCA1", "TP53", "EGFR"]
    }
)
```

<Note>
  **v0.5.0 fix:** `NERExtractor(method="llm")` no longer silently falls back to pattern extraction on custom gateways. The `response_format=json_object` parameter is now conditionally omitted for incompatible gateways, with a plain `generate()` + JSON parsing fallback applied automatically.
</Note>

## RelationExtractor

```python
from semantica.semantic_extract import RelationExtractor

rel = RelationExtractor(method="llm", llm_provider=llm, max_retries=3)
relationships = rel.extract(text, entities=entities)
```

Output format:

```python
[
    {"subject": "Steve Jobs", "predicate": "founded",    "object": "Apple Inc.", "confidence": 0.92},
    {"subject": "Apple Inc.", "predicate": "located_in", "object": "Cupertino",  "confidence": 0.89}
]
```

Available methods: `"rule"` (pattern-based), `"ml"` (REBEL model), `"llm"`.

## TripletExtractor

Generate RDF-ready `(subject, predicate, object)` triplets directly from text:

```python
from semantica.semantic_extract import TripletExtractor

trip = TripletExtractor(method="llm", llm_provider=llm)
triplets = trip.extract(text)
# → [{"subject": "Steve Jobs", "predicate": "founded", "object": "Apple Inc.", ...}]
```

Triplets are suitable for loading directly into a triplet store or knowledge graph.

## EventExtractor

Detect events with participants and temporal context:

```python
from semantica.semantic_extract import EventExtractor

extractor = EventExtractor(method="llm", llm_provider=llm)
events = extractor.extract(text)
```

Output includes: event type, participants (with roles), temporal information, location, and confidence score.

## CoreferenceResolver

Resolve pronoun and alias references to canonical entities before extraction:

```python
from semantica.semantic_extract import CoreferenceResolver

resolver = CoreferenceResolver()
resolved_text = resolver.resolve(
    "Apple Inc. was founded in 1976. The company is headquartered in Cupertino."
)
# "Apple Inc." replaces "The company" for consistent downstream extraction
```

## Batch Processing

All extractors support batch input for efficient large-scale processing:

```python
texts = ["Text 1...", "Text 2...", "Text 3..."]

ner = NERExtractor(method="llm", llm_provider=llm)
batch_results = ner.extract_batch(texts, batch_size=10)
```

## Using All Extractors Together

The standard extraction pipeline — entities → relationships → triplets:

```python
from semantica.semantic_extract import NERExtractor, RelationExtractor, TripletExtractor
from semantica.llms import Groq
import os

llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))

ner  = NERExtractor(method="llm",      llm_provider=llm, max_retries=3)
rel  = RelationExtractor(method="llm", llm_provider=llm, max_retries=3)
trip = TripletExtractor(method="llm",  llm_provider=llm, max_retries=3)

entities      = ner.extract(text)
relationships = rel.extract(text, entities=entities)
triplets      = trip.extract(text)
```

## Extraction Method Comparison

| Method | Speed | Cost | Accuracy | Custom Types |
| ------ | ----- | ---- | -------- | ------------ |
| `pattern` | Very fast | Free | Medium | Yes (dictionary) |
| `ml` | Fast | Free | High | Limited |
| `llm` | Medium | API cost | Highest | Yes (schema) |

<CardGroup cols={2}>
  <Card title="LLM Providers" icon="microchip" href="llms">
    Configure which LLM is used for extraction.
  </Card>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    Build graphs from extracted entities and relationships.
  </Card>
  <Card title="Parse Module" icon="file-lines" href="parse">
    Parse documents before extraction.
  </Card>
  <Card title="Deduplication" icon="copy" href="deduplication">
    Resolve duplicate entities after extraction.
  </Card>
</CardGroup>
