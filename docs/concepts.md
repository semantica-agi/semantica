---
title: "Core Concepts"
description: "The fundamental ideas behind Semantica — knowledge graphs, reasoning, provenance, and temporal intelligence explained."
icon: "book-open"
---

<Tip>
  New here? Start with [Getting Started](getting-started) for hands-on examples, then return here for deeper understanding.
</Tip>

Semantica transforms unstructured data — documents, web pages, reports, databases — into **knowledge graphs**: structured representations that AI systems can query, reason about, and trace back to sources.

At its core, Semantica adds a **context and intelligence layer** on top of your existing AI stack. It doesn't replace LangChain, LlamaIndex, or your LLM provider — it makes their outputs accountable.

## Knowledge Graphs

The foundation of everything in Semantica. A knowledge graph stores information as three building blocks:

- **Nodes (entities)** — people, companies, locations, events, concepts
- **Edges (relationships)** — `works_for`, `located_in`, `founded_by`
- **Properties** — name, date, confidence score, source URL

This structure makes knowledge **searchable**, **connectable**, **queryable**, and — critically — **explainable**: every answer can be traced back to the facts and relationships that produced it.

## Entity Extraction (NER)

Scanning text to find and classify real-world entities.

```python
# Input: "Apple Inc. was founded by Steve Jobs in 1976 in Cupertino."
{
    "entities": [
        {"text": "Apple Inc.",  "type": "ORGANIZATION", "confidence": 0.98},
        {"text": "Steve Jobs",  "type": "PERSON",       "confidence": 0.99},
        {"text": "1976",        "type": "DATE",         "confidence": 0.95},
        {"text": "Cupertino",   "type": "LOCATION",     "confidence": 0.97}
    ]
}
```

Each entity gets a type, confidence score, and a link to its source document. Three extraction methods are available:

- **`"pattern"`** — fast, regex-based, no API key required
- **`"ml"`** — local ML model, higher accuracy
- **`"llm"`** — LLM-powered, highest accuracy, supports all 8 providers

## Relationship Extraction

Finding how entities connect to each other.

```python
{
    "relationships": [
        {"subject": "Steve Jobs", "predicate": "founded",    "object": "Apple Inc.", "confidence": 0.92},
        {"subject": "Apple Inc.", "predicate": "located_in", "object": "Cupertino",  "confidence": 0.89}
    ]
}
```

Relationships can be extracted via rule-based methods, ML models, or LLMs — each producing typed triplets with confidence scores and source attribution.

## Embeddings

Embeddings convert text into numerical vectors so AI systems can measure semantic similarity — finding related concepts even when the exact words differ.

Semantica uses embeddings for:

- **Semantic search** — retrieve by meaning, not just keywords
- **Entity resolution** — match the same entity across different sources
- **Precedent search** — find similar past decisions
- **GraphRAG retrieval** — hybrid vector + graph traversal

**Supported models:** Sentence-Transformers, FastEmbed, OpenAI, BGE

## GraphRAG

GraphRAG (Graph-Augmented Retrieval Augmented Generation) enhances LLM responses by grounding them in a structured knowledge graph rather than raw text chunks alone.

**How it works:**

1. User submits a query
2. Semantica retrieves relevant graph context — entities, relationships, reasoning paths
3. The LLM generates a response grounded in that context
4. Every claim in the response links back to a source node in the graph

This eliminates the hallucination and traceability problems of standard RAG.

## Ontology

An ontology defines the schema and rules for your knowledge — what entity types exist, which relationships are valid, and what constraints apply.

```python
ontology = {
    "classes": ["Person", "Organization", "Location"],
    "relationships": ["works_for", "located_in", "founded_by"],
    "rules": {
        "Person":       ["must_have_name"],
        "Organization": ["must_have_name", "can_have_founding_date"]
    }
}
```

Semantica can auto-generate ontologies from your knowledge graph or import existing OWL/RDF/Turtle ontologies. The **Ontology Hub** (v0.5.0) adds a visual editor, SHACL Studio, alignment authoring, and a live health dashboard.

## Reasoning & Inference

Semantica includes multiple reasoning engines to derive new knowledge from existing facts.

```text
Known:    Steve Jobs founded Apple Inc.
Known:    Apple Inc. is headquartered in Cupertino
Inferred: Steve Jobs has a connection to Cupertino
```

| Engine | Description |
| ------ | ----------- |
| Forward chaining | Applies rules repeatedly until no new facts can be derived |
| Rete network | Efficient pattern matching for large rule sets |
| Deductive | Classical deductive reasoning |
| Abductive | Infers the most likely explanation |
| SPARQL | Query-based inference over RDF graphs |
| Datalog | Recursive Horn clause rules with fixpoint semantics (v0.4.0) |

All engines produce **explainable inference paths**, not black-box conclusions.

## Temporal Intelligence

Knowledge changes over time. Temporal graphs attach `valid_from` / `valid_until` windows to nodes and edges, enabling point-in-time queries and historical analysis.

```python
from semantica.kg import TemporalKnowledgeGraph
from datetime import datetime

tkg = TemporalKnowledgeGraph()
tkg.add_node("ceo_role", valid_from=datetime(2020, 1, 1), valid_until=datetime(2023, 6, 1))

# Query the graph as it existed on a specific date
snapshot = tkg.at(datetime(2021, 6, 15))
```

**Features:** Allen interval algebra (all 13 relations), OWL-Time export, `recorded_at` stamping, temporal provenance.

**Common uses:** tracking company leadership changes, policy evolution, research timelines, financial instrument histories.

## Distance Intelligence

Explore the semantic neighborhood of any entity in your graph. Useful for understanding what's conceptually close, detecting clusters, and visualizing knowledge topology.

```python
from semantica.kg import DistanceCalculator

calc         = DistanceCalculator(graph)
neighborhood = calc.semantic_neighborhood("Apple Inc.", radius=0.4)
matrix       = calc.distance_matrix(["Apple Inc.", "Google", "Microsoft"])
```

**Features:** N×N distance matrices, ego-mode visualization, distance band classification (`near` / `mid` / `far`), embedding cache optimization.

## Deduplication & Entity Resolution

Real-world data contains the same entity under many names — "Apple", "Apple Inc.", "Apple Computer Inc." Semantica's deduplication pipeline detects these, merges attributes, resolves conflicts, and preserves the original source provenance.

**Strategies:**

- **v1** — Jaro-Winkler similarity, suitable for small datasets
- **`blocking_v2`** — candidate blocking for large corpora
- **`hybrid_v2`** — combines blocking with semantic matching
- **`semantic_v2`** — pure embedding-based resolution, up to 7x faster than v1

## Provenance & Auditability

Every fact in Semantica links back to:

- The source document it came from
- The extraction method used
- The ontology rules applied
- The reasoning steps that produced any inference

This is W3C PROV-O compliant lineage — suitable for regulated industries that require audit trails (HIPAA, SOX, GDPR, FDA 21 CFR Part 11).

## Decision Intelligence

Every agent decision is a first-class object in Semantica — recorded, causally linked, and searchable by precedent.

```python
decision_id = context.record_decision(
    category="model_selection",
    scenario="Choose LLM for production pipeline",
    reasoning="GPT-4 benchmark advantage justifies 3x cost increase",
    outcome="selected_gpt4",
    confidence=0.91,
)

precedents = context.find_precedents("model selection reasoning", limit=5)
influence  = context.analyze_decision_influence(decision_id)
```

This prevents inconsistent decisions, enables audits, and lets agents learn from their own history.

## Conflict Detection

When multiple sources disagree on the same fact, Semantica flags and resolves the conflict rather than silently picking one value.

**Resolution strategies:**

- Prefer the most recent source
- Prefer the most reliable source
- Majority vote across sources
- Flag for manual review

<CardGroup cols={2}>
  <Card title="Quickstart Tutorial" icon="play" href="quickstart">
    Build a full pipeline with code.
  </Card>
  <Card title="Modules Guide" icon="puzzle-piece" href="modules">
    Every module explained with examples.
  </Card>
  <Card title="Use Cases" icon="briefcase" href="use-cases">
    Real-world domain examples.
  </Card>
  <Card title="API Reference" icon="code" href="reference/context">
    Complete technical reference.
  </Card>
</CardGroup>
