---
title: "Getting Started"
description: "The context and intelligence layer for AI — turning raw data into explainable, auditable knowledge graphs."
icon: "rocket"
---

<Tip>
  Already installed? Jump to [Quickstart](quickstart). Need setup help first? Start with [Installation](installation).
</Tip>

---

## What You Can Build

<CardGroup cols={2}>
  <Card title="GraphRAG Systems" icon="diagram-project">
    Enhanced retrieval with semantic graph reasoning — ground LLM responses in traceable, structured knowledge.
  </Card>
  <Card title="Accountable AI Agents" icon="robot">
    Agents with structured decision history, causal chains, and precedent search. Every choice is recorded and auditable.
  </Card>
  <Card title="Production Knowledge Graphs" icon="sitemap">
    Build, validate, and maintain enterprise-grade semantic knowledge bases from multi-source data.
  </Card>
  <Card title="Compliance-Ready AI" icon="shield-check">
    W3C PROV-O provenance on every fact. HIPAA, SOX, GDPR, FDA 21 CFR Part 11 infrastructure built in.
  </Card>
</CardGroup>

---

## Installation

```bash
pip install semantica
```

With all optional dependencies:

```bash
pip install semantica[all]
```

For virtual environments and platform-specific setup, see the full [Installation](installation).

Verify:

```python
import semantica
print(semantica.__version__)
```

---

## Quick Start

<CodeGroup>

```python Knowledge Graph
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder

# Ingest → Parse → Extract → Build
ingestor = FileIngestor()
sources = ingestor.ingest("data/sample.pdf")

parser = DocumentParser()
parsed = parser.parse(sources[0])

ner = NERExtractor()
entities = ner.extract(parsed)

rel = RelationExtractor()
relationships = rel.extract(parsed, entities=entities)

graph = GraphBuilder(merge_entities=True).build(
    entities=entities, relationships=relationships
)
print(f"{len(graph.nodes)} nodes, {len(graph.edges)} edges")
```

```python Agent Context
from semantica.context import AgentContext, ContextGraph
from semantica.vector_store import VectorStore

context = AgentContext(
    vector_store=VectorStore(backend="faiss", dimension=768),
    knowledge_graph=ContextGraph(advanced_analytics=True),
    decision_tracking=True,
)

# Store a memory with provenance
context.store("GPT-4 outperforms GPT-3.5 on reasoning benchmarks by 40%")

# Record a decision with causal chain
decision_id = context.record_decision(
    category="model_selection",
    scenario="Choose LLM for production pipeline",
    reasoning="GPT-4 benchmark advantage justifies cost increase",
    outcome="selected_gpt4",
    confidence=0.91,
)

# Find similar past decisions
precedents = context.find_precedents("model selection", limit=5)
```

```python GraphRAG
from semantica.context import AgentContext, ContextGraph
from semantica.vector_store import VectorStore
from semantica.reasoning import ReasoningEngine

context = AgentContext(
    vector_store=VectorStore(backend="faiss", dimension=768),
    knowledge_graph=ContextGraph(advanced_analytics=True),
)

# Load your knowledge graph
context.load_graph("company_kg.json")

# Multi-hop GraphRAG query
result = context.query(
    "What companies were founded by people who worked at Apple?",
    mode="graphrag",
    reasoning=True,
)

# Every claim links back to a source node
for claim in result.claims:
    print(f"{claim.text}  →  source: {claim.source_node}")
```

</CodeGroup>

---

## Core Architecture

Semantica uses a modular, layered architecture — import only what you need.

| Layer | Modules | Purpose |
|-------|---------|---------|
| **Input** | `ingest`, `parse`, `split`, `normalize` | Load and prepare data |
| **Semantic** | `semantic_extract`, `kg`, `ontology`, `reasoning` | Extract meaning |
| **Storage** | `embeddings`, `vector_store`, `graph_store` | Persist knowledge |
| **Quality** | `deduplication`, `conflicts` | Validate and clean |
| **Context** | `context`, `provenance`, `change_management` | Track decisions and lineage |
| **Output** | `export`, `visualization`, `pipeline` | Deliver results |

---

## Next Steps

<CardGroup cols={2}>
  <Card title="Core Concepts" icon="book-open" href="concepts">
    Knowledge graphs, ontologies, and reasoning explained in depth.
  </Card>
  <Card title="Quickstart Tutorial" icon="play" href="quickstart">
    Full 6-step pipeline with `<Steps>` walkthrough.
  </Card>
  <Card title="Cookbook" icon="flask" href="cookbook">
    40+ domain-specific Jupyter notebook tutorials.
  </Card>
  <Card title="API Reference" icon="code" href="reference/context">
    Complete module documentation for every class and method.
  </Card>
</CardGroup>

---

## Help

<CardGroup cols={3}>
  <Card title="Discord" icon="discord" href="https://discord.gg/sV34vps5hH">
    Ask questions, share projects, get community support.
  </Card>
  <Card title="GitHub Issues" icon="github" href="https://github.com/semantica-agi/semantica/issues">
    Report bugs or request features.
  </Card>
  <Card title="FAQ" icon="circle-question" href="faq">
    Common questions answered.
  </Card>
</CardGroup>
