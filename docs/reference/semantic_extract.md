---
title: "Semantic Extract Module"
description: "Named entity recognition, relation extraction, event detection, and triplet generation."
icon: "magnifying-glass-chart"
---

`semantica.semantic_extract` extracts structured information from unstructured text — the foundation of every knowledge graph in Semantica. All extractors support three modes: pattern-based (no API key), ML-based, and LLM-based.

## Quick Start

<Steps>
  <Step title="Resolve coreferences (optional but recommended)">
    ```python
    from semantica.semantic_extract import CoreferenceResolver

    resolver     = CoreferenceResolver()
    resolved_text = resolver.resolve(
        "Apple Inc. was founded in 1976. The company is headquartered in Cupertino."
    )
    # "Apple Inc." replaces "The company" — consistent downstream extraction
    ```
  </Step>
  <Step title="Extract named entities">
    ```python
    from semantica.semantic_extract import NERExtractor
    from semantica.llms import Groq
    import os

    llm      = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    ner      = NERExtractor(method="llm", llm_provider=llm, max_retries=3)
    entities = ner.extract(resolved_text)
    # → [{"text": "Apple Inc.", "type": "ORGANIZATION", "confidence": 0.98, ...}]
    ```
  </Step>
  <Step title="Extract relationships between entities">
    ```python
    from semantica.semantic_extract import RelationExtractor

    rel           = RelationExtractor(method="llm", llm_provider=llm, max_retries=3)
    relationships = rel.extract(resolved_text, entities=entities)
    # → [{"subject": "Steve Jobs", "predicate": "founded", "object": "Apple Inc.", ...}]
    ```
  </Step>
  <Step title="Validate and filter before building the graph">
    ```python
    from semantica.semantic_extract import ExtractionValidator

    validator = ExtractionValidator(min_confidence=0.7)
    valid_entities, _ = validator.validate_entities(entities)
    valid_rels,     _ = validator.validate_relations(relationships)
    ```
  </Step>
</Steps>

## What You Get

<CardGroup cols={2}>
  <Card title="NERExtractor" icon="tag">
    Named entity recognition: Person, Organization, Location, Date, and custom types.
  </Card>
  <Card title="RelationExtractor" icon="arrow-right-arrow-left">
    Typed semantic relationships between entities (`founded_by`, `located_in`, etc.).
  </Card>
  <Card title="TripletExtractor" icon="table">
    Direct `(subject, predicate, object)` triplet generation for RDF-ready output.
  </Card>
  <Card title="EventDetector" icon="calendar">
    Event detection with participants, temporal context, and confidence scores.
  </Card>
  <Card title="CoreferenceResolver" icon="link">
    Resolve "Apple" and "the company" to the same entity across a document.
  </Card>
  <Card title="SemanticAnalyzer" icon="chart-scatter">
    Semantic role labeling, clustering, and entity similarity analysis.
  </Card>
</CardGroup>

<img src="/assets/img/diagrams/extraction-pipeline.svg" alt="Semantic extraction pipeline: raw text fans into NER, Relation, and Coreference extractors, then merges into a Triplet Generator" style={{ width: '100%', borderRadius: '12px', margin: '0 0 24px' }} />

## Extraction Methods

<Tabs>
  <Tab title="LLM (best accuracy)">
    Uses a language model to extract entities and relationships. Handles complex schemas, novel entity types, and domain-specific language. Requires an API key.

    ```python
    from semantica.semantic_extract import NERExtractor
    from semantica.llms import Groq
    import os

    llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    ner = NERExtractor(method="llm", llm_provider=llm, max_retries=3)

    entities = ner.extract("Apple Inc. was founded by Steve Jobs in Cupertino in 1976.")
    ```

    <Note>
      **v0.5.0 fix:** `NERExtractor(method="llm")` no longer silently falls back to pattern extraction on custom gateways. The `response_format=json_object` parameter is now conditionally omitted for incompatible gateways, with a plain `generate()` + JSON parsing fallback applied automatically.
    </Note>

    Works with every Semantica LLM provider — swap `Groq` for `Anthropic`, `OpenAI`, `Gemini`, `Ollama`, `HuggingFace`, `DeepSeek`, or `Novita` with a one-line change:

    ```python
    from semantica.llms import Anthropic
    llm = Anthropic(model="claude-opus-4-7", api_key=os.getenv("ANTHROPIC_API_KEY"))
    ner = NERExtractor(method="llm", llm_provider=llm)
    ```
  </Tab>
  <Tab title="ML (fast, free)">
    Uses a pre-trained BERT-based NER model. High accuracy for standard entity types (Person, Organization, Location, Date) at zero API cost.

    ```python
    ner      = NERExtractor(method="ml", model="dslim/bert-large-NER")
    entities = ner.extract(text)
    ```

    For relations, the ML backend uses the REBEL model:

    ```python
    rel           = RelationExtractor(method="ml")
    relationships = rel.extract(text, entities=entities)
    ```

    Best for: high-throughput extraction where API cost matters and entity types are standard CoNLL/OntoNotes categories.
  </Tab>
  <Tab title="Pattern (zero cost)">
    Dictionary and regex matching — extremely fast, zero API cost, zero model loading. Accuracy depends entirely on your dictionaries.

    ```python
    ner = NERExtractor(
        method="pattern",
        custom_entities={
            "DRUG": ["aspirin", "ibuprofen", "metformin"],
            "GENE": ["BRCA1", "TP53", "EGFR"]
        }
    )
    entities = ner.extract(text)
    ```

    For relations, uses hand-crafted rules:

    ```python
    rel = RelationExtractor(method="rule")
    ```

    Best for: known entity sets (drug names, product codes, gene symbols), no-API-key environments, or as a first pass before LLM validation.

    <Warning>
      The pattern matcher is **case-sensitive and whitespace-sensitive**. Normalize text first with `TextNormalizer` so "BRCA1" and "brca1" both match. For fuzzy matching, use `method="ml"`.
    </Warning>
  </Tab>
</Tabs>

### Method Comparison

| Method | Speed | Cost | Accuracy | Custom Types | Best For |
| ------ | ----- | ---- | -------- | ------------ | -------- |
| `pattern` | Very fast | Free | Medium | Yes (dictionary) | Known entity sets, no-API environments |
| `ml` | Fast | Free | High | Limited | Standard types at scale, no API budget |
| `llm` | Medium | API cost | Highest | Yes (schema) | Complex schemas, novel types, best accuracy |

## NERExtractor

```python
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

Batch processing for large corpora:

```python
texts         = ["Text 1...", "Text 2...", "Text 3..."]
batch_results = ner.extract_batch(texts, batch_size=10)
```

## RelationExtractor

```python
relationships = rel.extract(text, entities=entities)
```

Output format:

```python
[
    {"subject": "Steve Jobs", "predicate": "founded",    "object": "Apple Inc.", "confidence": 0.92},
    {"subject": "Apple Inc.", "predicate": "located_in", "object": "Cupertino",  "confidence": 0.89}
]
```

<Tip>
  Always pass `entities=entities` from your NER output. This anchors relationships to known entity spans — improving accuracy and eliminating hallucinated entity names.
</Tip>

## TripletExtractor

Generate RDF-ready `(subject, predicate, object)` triplets directly from text:

```python
from semantica.semantic_extract import TripletExtractor

trip     = TripletExtractor(method="llm", llm_provider=llm)
triplets = trip.extract(text)
# → [{"subject": "Steve Jobs", "predicate": "founded", "object": "Apple Inc.", ...}]
```

Triplets are suitable for loading directly into a triplet store or knowledge graph without a separate relation extraction step.

## EventDetector

Detect events with participants and temporal context:

```python
from semantica.semantic_extract import EventDetector

extractor = EventDetector(method="llm", llm_provider=llm)
events    = extractor.extract(text)
```

Output includes: event type, participants (with roles), temporal information, location, and confidence score.

## SemanticAnalyzer

Semantic role labeling, clustering, and similarity analysis on extracted content:

```python
from semantica.semantic_extract import SemanticAnalyzer

analyzer = SemanticAnalyzer()

# Who did what to whom
roles = analyzer.label_roles(text)
# → [{"agent": "Apple", "action": "acquired", "patient": "Intel's modem unit"}]

# Group similar entities
clusters = analyzer.cluster_entities(entities, n_clusters=5)
# → [{"cluster_id": 0, "entities": ["Apple Inc.", "Apple", "AAPL"]}, ...]

# Pairwise semantic similarity
score = analyzer.calculate_similarity(entity_a, entity_b)
# → 0.87
```

| Method | Returns | Description |
| ------ | ------- | ----------- |
| `label_roles(text)` | `List[Dict]` | Semantic role labeling (agent, action, patient) |
| `cluster_entities(entities, n_clusters)` | `List[Cluster]` | Group similar entities |
| `calculate_similarity(a, b)` | `float` | Cosine similarity between entity embeddings |
| `analyze_sentiment(text)` | `Dict` | Sentiment and subjectivity scores |

## SemanticNetworkExtractor

Extracts a full semantic network (nodes + typed edges) from text in one pass:

```python
from semantica.semantic_extract import SemanticNetworkExtractor

extractor = SemanticNetworkExtractor(method="llm", llm_provider=llm)
network   = extractor.extract_network(text)

print(f"Nodes: {len(network.nodes)}")
print(f"Edges: {len(network.edges)}")

for edge in network.edges:
    print(f"  {edge.source} --[{edge.relation}]--> {edge.target}  (conf: {edge.confidence:.2f})")
```

<Accordion title="SemanticNetwork schema">

```python
@dataclass
class SemanticNetwork:
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]

@dataclass
class NetworkNode:
    id:         str
    label:      str            # entity type (PERSON, ORG, etc.)
    properties: Dict[str, Any]

@dataclass
class NetworkEdge:
    source:     str
    target:     str
    relation:   str            # e.g. "founded_by", "located_in"
    confidence: float
    metadata:   Dict[str, Any]
```

</Accordion>

## ExtractionValidator

Validates extraction quality and filters low-confidence results:

```python
from semantica.semantic_extract import ExtractionValidator

validator = ExtractionValidator(
    min_confidence=0.7,       # drop entities below this score
    require_entity_text=True, # entity text must be non-empty
    max_entity_length=100,    # discard suspiciously long entities
)

valid_entities, rejected = validator.validate_entities(entities)
valid_rels,     rejected = validator.validate_relations(relationships)

report = validator.get_quality_report(entities, relationships)
print(f"Precision estimate: {report['precision']:.2f}")
```

## Tips and Common Pitfalls

<Tip>
  **Run `CoreferenceResolver` before extraction.** If a paragraph says "Apple Inc. was founded in 1976. The company launched..." without resolving "the company" → "Apple Inc.", your extractor may miss the second entity or create a phantom "The company" node.
</Tip>

<Tip>
  **Always pass `entities=` to `RelationExtractor`.** Passing the entity list from NER output anchors relationships to known entity spans — improving accuracy and eliminating hallucinated entity names.
</Tip>

<Warning>
  **Validate before building the graph.** Use `ExtractionValidator(min_confidence=0.7)` to drop low-confidence entities before they reach `GraphBuilder`. Noisy extractions produce noisy graphs that corrupt analytics and search.
</Warning>

<Tip>
  **Set `max_retries=3` for LLM extractors.** API calls fail transiently. Setting `max_retries=3` prevents pipeline crashes on flaky network conditions without slowing down the happy path.
</Tip>

<Warning>
  **Don't mix extraction methods mid-pipeline.** If you extract entities with `pattern` and relations with `llm`, entity names in the relation output may not match the pattern-extracted entity IDs — causing alignment failures in `GraphBuilder`. Use the same method throughout, or normalize entity names before the relation step.
</Warning>

<Tip>
  **Batch large inputs.** Call `ner.extract_batch(texts, batch_size=10)` rather than looping over individual texts. Batch mode is significantly faster for both ML (GPU batching) and LLM (fewer API round-trips with prompt packing).
</Tip>

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
