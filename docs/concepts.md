# Core Concepts

The fundamental ideas behind Semantica — explained plainly.

!!! tip "New here?"
    Start with [Getting Started](getting-started.md) for hands-on examples, then come back to this page for deeper understanding.

---

## What is Semantica?

Semantica transforms unstructured data (documents, web pages, reports, databases) into **knowledge graphs** — structured representations that AI systems can query, reason about, and trace back to sources.

At its core, Semantica adds a **context and intelligence layer** on top of your existing AI stack: it doesn't replace LangChain, LlamaIndex, or your LLM provider — it makes their outputs accountable.

---

## Knowledge Graphs

The foundation of everything in Semantica.

A knowledge graph stores information as:

- **Nodes (entities)** — people, companies, locations, events, concepts
- **Edges (relationships)** — `works_for`, `located_in`, `founded_by`
- **Properties** — name, date, confidence score, source URL

This structure makes knowledge **searchable**, **connectable**, **queryable**, and — critically — **explainable**: every answer can be traced back to the facts and relationships that produced it.

---

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

Each entity gets a type, confidence score, and a link to its source document.

---

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

Relationships can be extracted via rule-based methods, ML models, or LLMs (with `"llm_typed"` metadata).

---

## Embeddings

Embeddings convert text into numerical vectors so that AI systems can measure semantic similarity — finding related concepts even when the exact words differ.

Semantica uses embeddings for:

- **Semantic search** — retrieve by meaning, not just keywords
- **Entity resolution** — match the same entity across different sources
- **Precedent search** — find similar past decisions
- **GraphRAG retrieval** — hybrid vector + graph traversal

---

## GraphRAG

GraphRAG (Graph-Augmented Retrieval Augmented Generation) enhances LLM responses by grounding them in a structured knowledge graph rather than raw text chunks alone.

How it works:

1. User submits a query
2. Semantica retrieves relevant graph context (entities, relationships, reasoning paths)
3. The LLM generates a response grounded in that context
4. Every claim in the response links back to a source node in the graph

This eliminates the hallucination and traceability problems of standard RAG.

---

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

Semantica can auto-generate ontologies from your knowledge graph, or import existing OWL/RDF/Turtle ontologies.

---

## Reasoning & Inference

Semantica includes multiple reasoning engines to derive new knowledge from existing facts.

```
Known:    Steve Jobs founded Apple Inc.
Known:    Apple Inc. is headquartered in Cupertino
Inferred: Steve Jobs has a connection to Cupertino
```

Supported engines: forward chaining, Rete network, deductive, abductive, and SPARQL reasoning — all producing **explainable inference paths**, not black-box conclusions.

---

## Temporal Graphs

Knowledge changes over time. Temporal graphs attach `valid_from` / `valid_until` windows to nodes and edges, enabling point-in-time queries and historical analysis.

Common uses: tracking company leadership changes, policy evolution, research timelines, financial instrument histories.

---

## Deduplication & Entity Resolution

Real-world data contains the same entity under many names — "Apple", "Apple Inc.", "Apple Computer Inc." Semantica's deduplication pipeline detects these, merges attributes, resolves conflicts, and preserves the original source provenance.

Strategies: Jaro-Winkler similarity (v1), `blocking_v2`, `hybrid_v2`, `semantic_v2` (v2 — up to 7x faster).

---

## Provenance & Auditability

Every fact in Semantica links back to:

- The source document it came from
- The extraction method used
- The ontology rules applied
- The reasoning steps that produced any inference

This is W3C PROV-O compliant lineage — suitable for regulated industries that require audit trails.

---

## Conflict Detection

When multiple sources disagree on the same fact, Semantica flags and resolves the conflict rather than silently picking one value.

Resolution strategies: prefer most recent, prefer most reliable source, majority vote, or flag for manual review.

---

## Next Steps

- [Quickstart Tutorial](quickstart.md) — build a full pipeline with code
- [Modules Guide](modules.md) — every module explained
- [Use Cases](use-cases.md) — real-world domain examples
- [API Reference](reference/core.md) — complete technical reference
