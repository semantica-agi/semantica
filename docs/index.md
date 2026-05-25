---
title: "Semantica"
description: "The Accountability and Context Layer for AI — Context Graphs · Decision Intelligence · Full Provenance"
---

<Info>
  **v0.5.0 is live** — Ontology Hub, Distance Intelligence, SHACL Studio, Parquet & XML ingestion, 12 security fixes. [What's new →](#whats-new)
</Info>

> Most AI agents act without a trail. Semantica adds the layer your stack is missing: structured context graphs, auditable decision records, and full provenance from every output back to its source — so your AI isn't just powerful, it's **accountable**.

## The Problem

AI agents today are powerful but not trustworthy. Five structural gaps make them impossible to deploy in regulated environments:

<CardGroup cols={2}>
  <Card title="No memory structure" icon="brain">
    Agents store embeddings, not meaning. There's no way to ask *why* something was recalled or trace a fact to its source.
  </Card>
  <Card title="No decision trail" icon="clock-rotate-left">
    Agents act continuously but record nothing. When something breaks, there's no history to debug or audit.
  </Card>
  <Card title="No provenance" icon="link-slash">
    Outputs can't be traced back to source facts. In healthcare, finance, and legal, this is a hard compliance blocker.
  </Card>
  <Card title="No reasoning transparency" icon="eye-slash">
    Black-box answers with zero explanation of how a conclusion was reached.
  </Card>
  <Card title="No conflict detection" icon="triangle-exclamation">
    Contradictory facts silently coexist in vector stores, producing unpredictable and inconsistent outputs.
  </Card>
</CardGroup>

These aren't edge cases. They're why AI cannot be deployed in healthcare, finance, legal, and government without custom guardrails built from scratch.

## The Solution

Semantica is the **accountability and context layer** you add on top of your existing AI stack. Not a replacement for LangChain or LlamaIndex — the infrastructure that makes their outputs trustworthy.

<CardGroup cols={2}>
  <Card title="Context Graphs" icon="diagram-project">
    A structured, queryable graph of everything your agent knows, decides, and reasons about. Persistent across runs.
  </Card>
  <Card title="Decision Intelligence" icon="check-circle">
    Every decision is a first-class object: recorded, causally linked, searchable by precedent, and analyzable for downstream impact.
  </Card>
  <Card title="Full Provenance" icon="shield-check">
    Every fact links back to its source. W3C PROV-O compliant. Full lineage from ingestion to inference.
  </Card>
  <Card title="Reasoning Engines" icon="microchip">
    Forward chaining, Rete, deductive, abductive, SPARQL, Datalog. Explainable paths, not black boxes.
  </Card>
  <Card title="Temporal Intelligence" icon="clock">
    Point-in-time queries, Allen interval algebra, temporal provenance, OWL-Time export.
  </Card>
  <Card title="Ontology Hub" icon="sitemap">
    Visual editor, SHACL Studio, alignment authoring, health dashboard. Full ontology lifecycle in the browser.
  </Card>
</CardGroup>

Works alongside any LLM provider and any agent framework.

<img src="/assets/img/diagrams/architecture-overview.svg" alt="Semantica four-layer architecture: Ingestion → Processing → Intelligence → Application" style={{ width: '100%', borderRadius: '12px', margin: '24px 0' }} />

## Quick Start

```bash
pip install semantica
```

<CodeGroup>

```python OpenAI
from semantica.context import AgentContext, ContextGraph
from semantica.vector_store import VectorStore
from semantica.llms import OpenAI

context = AgentContext(
    vector_store=VectorStore(backend="faiss", dimension=1536),
    knowledge_graph=ContextGraph(advanced_analytics=True),
    decision_tracking=True,
    llm=OpenAI(model="gpt-4o"),
)

context.store("GPT-4 outperforms GPT-3.5 on reasoning benchmarks by 40%")

decision_id = context.record_decision(
    category="model_selection",
    scenario="Choose LLM for production reasoning pipeline",
    reasoning="GPT-4 benchmark advantage justifies 3x cost increase",
    outcome="selected_gpt4",
    confidence=0.91,
)

precedents = context.find_precedents("model selection reasoning", limit=5)
influence  = context.analyze_decision_influence(decision_id)
```

```python Anthropic
from semantica.context import AgentContext, ContextGraph
from semantica.vector_store import VectorStore
from semantica.llms import LiteLLM
import os

context = AgentContext(
    vector_store=VectorStore(backend="faiss", dimension=1024),
    knowledge_graph=ContextGraph(advanced_analytics=True),
    decision_tracking=True,
    llm=LiteLLM(model="anthropic/claude-opus-4-7", api_key=os.getenv("ANTHROPIC_API_KEY")),
)

context.store("Claude excels at long-context reasoning and code generation")

decision_id = context.record_decision(
    category="model_selection",
    scenario="Choose LLM for document analysis pipeline",
    reasoning="Claude's 200k context window eliminates chunking overhead",
    outcome="selected_claude",
    confidence=0.94,
)

precedents = context.find_precedents("document analysis model", limit=5)
```

```python Ollama (Local)
from semantica.context import AgentContext, ContextGraph
from semantica.vector_store import VectorStore
from semantica.llms import LiteLLM

context = AgentContext(
    vector_store=VectorStore(backend="faiss", dimension=768),
    knowledge_graph=ContextGraph(advanced_analytics=True),
    decision_tracking=True,
    llm=LiteLLM(model="ollama/llama3.2", base_url="http://localhost:11434"),
)

# Fully local — no data leaves your infrastructure
context.store("Local LLMs enable air-gapped compliance deployments")

decision_id = context.record_decision(
    category="deployment_model",
    scenario="Choose inference strategy for on-prem environment",
    reasoning="Air-gap requirement eliminates cloud API options",
    outcome="local_inference",
    confidence=0.99,
)
```

</CodeGroup>

<CardGroup cols={3}>
  <Card title="Full Quickstart" icon="rocket" href="quickstart">
    Step-by-step pipeline walkthrough.
  </Card>
  <Card title="Cookbook" icon="flask" href="cookbook">
    40+ real-world Jupyter notebooks.
  </Card>
  <Card title="Join Discord" icon="discord" href="https://discord.gg/sV34vps5hH">
    Community chat and support.
  </Card>
</CardGroup>

## What's New

<AccordionGroup>

<Accordion title="v0.5.0 — Ontology Hub & Distance Intelligence" icon="star" defaultOpen={true}>

Released **May 11, 2026**

| Area | Highlights |
|------|------------|
| **Ontology Hub** | Visual editor, SHACL Studio, alignment authoring, health dashboard, version control — full ontology lifecycle in the browser |
| **Distance Intelligence** | Semantic neighborhoods, N×N distance matrices, ego-mode visualization, distance band classification, embedding cache optimization |
| **Parquet Ingestion** | `ParquetIngestor` with PyArrow — single file, partitioned directories, Hive-style discovery, selective column reading |
| **XML Ingestion** | `XMLIngestor` with XXE-safe lxml backend, XSD/DTD validation, namespace handling, directory scanning |
| **Graph Explorer** | Landing page redesign, bidirectional path finding, indexed search (0.004ms on 118k nodes) |
| **Security** | 12 vulnerability fixes: eval injection, pickle deserialization, SQL injection, XXE, SSRF, ReDoS, path traversal |
| **Bug Fixes** | NER LLM silent fallback on enterprise gateways, ConflictDetector duplicate definition, Windows `[all]` install, cp1252 crash |

```bash
pip install semantica==0.5.0
```

</Accordion>

<Accordion title="v0.4.0 — Temporal Intelligence & Knowledge Explorer" icon="clock">

| Area | Highlights |
|------|------------|
| **Temporal Intelligence** | 6-PR system: temporal data model, point-in-time queries, Allen interval algebra (all 13 relations), OWL-Time export |
| **Knowledge Explorer API** | Full FastAPI backend — 99 tests, 12 export formats, WebSocket progress, thread-safe sessions, audit trail |
| **Ontology Foundations** | SHACL generation/validation, SKOS vocabulary, ontology alignment API, diff & migration tooling |
| **Datalog Reasoning** | Pure-Python bottom-up semi-naive fixpoint, recursive Horn clause rules, guaranteed termination |
| **Agno Integration** | 5 components: graph-backed memory, multi-hop GraphRAG, decision toolkit, KG toolkit, shared team context; 110 tests |

</Accordion>

</AccordionGroup>

## Start Here

<Steps>
  <Step title="Install">
    ```bash
    pip install semantica
    ```
    See [Installation](installation) for optional extras and environment setup.
  </Step>
  <Step title="Follow the Quickstart">
    Build a complete knowledge graph pipeline — ingest, extract, build, query — in [5 minutes](quickstart).
  </Step>
  <Step title="Learn the mental model">
    [Core Concepts](concepts) explains knowledge graphs, GraphRAG, provenance, and decision intelligence. Read this before the API reference.
  </Step>
  <Step title="Go deep on any module">
    Every module has a dedicated [reference page](reference/context) with class docs, parameter tables, and runnable examples.
  </Step>
</Steps>

<CardGroup cols={2}>
  <Card title="Installation" icon="download" href="installation">
    Get Semantica installed in under a minute.
  </Card>
  <Card title="Quickstart" icon="rocket" href="quickstart">
    Build a complete knowledge graph pipeline in 5 minutes.
  </Card>
  <Card title="Core Concepts" icon="book-open" href="concepts">
    The mental model behind the API.
  </Card>
  <Card title="API Reference" icon="rectangle-terminal" href="reference/context">
    Jump here for exact module, class, and method details.
  </Card>
  <Card title="Cookbook" icon="flask" href="cookbook">
    Explore domain notebooks once you have the basics working.
  </Card>
</CardGroup>

## Capabilities

<AccordionGroup>

<Accordion title="Context & Decision Intelligence" icon="brain">

- **Context Graphs** — structured, persistent graph of entities, relationships, and decisions
- **Decision tracking** — `record_decision()` with full lifecycle management and causal chains
- **Precedent search** — hybrid similarity search over past decisions for consistency
- **Influence analysis** — `analyze_decision_impact()`, `analyze_decision_influence()`
- **Temporal graphs** — `valid_from` / `valid_until` on nodes and edges, point-in-time queries
- **Distance Intelligence** — semantic neighborhoods, N×N distance matrices, ego-mode exploration

</Accordion>

<Accordion title="Knowledge Engineering" icon="diagram-project">

- **NER** — named entity recognition with pattern, ML, or LLM methods
- **Relation extraction** — typed triplets via LLM or rule-based methods
- **Deduplication v2** — `blocking_v2`, `hybrid_v2`, `semantic_v2` — up to 7x faster
- **Ontology Hub** — visual editor, SHACL Studio, alignments, health dashboard
- **Datalog reasoning** — recursive Horn clause rules with fixpoint semantics
- **SPARQL reasoning** — query-based inference over RDF graphs

</Accordion>

<Accordion title="Provenance & Auditability" icon="shield-check">

- **W3C PROV-O** — lineage tracking across all modules
- **Change management** — version control with SHA-256 checksums and audit trails
- **Temporal provenance** — `recorded_at` stamping, OWL-Time export
- **Compliance** — HIPAA, SOX, GDPR, FDA 21 CFR Part 11 infrastructure

</Accordion>

<Accordion title="Data Ingestion & Export" icon="database">

**Ingestion:** PDF, DOCX, HTML, JSON, CSV, Excel, PPTX, Parquet, XML, archives, web crawl, SQL, Snowflake, feeds, email, repositories, MCP

**Vector Stores:** FAISS, Pinecone, Weaviate, Qdrant, Milvus, PgVector, in-memory

**Graph Stores:** Neo4j, FalkorDB, Apache AGE, Amazon Neptune

**Export:** RDF (Turtle, JSON-LD, N-Triples, XML), Parquet, ArangoDB AQL, OWL ontologies

</Accordion>

</AccordionGroup>

## Module Reference

| Module | What it provides |
|--------|-----------------|
| `semantica.context` | Context graphs, agent memory, decision tracking, causal analysis, precedent search |
| `semantica.kg` | KG construction, graph algorithms, temporal model, Allen interval algebra |
| `semantica.semantic_extract` | NER, relation extraction, event extraction, triplet generation |
| `semantica.reasoning` | Forward chaining, Rete, deductive, abductive, SPARQL, Datalog |
| `semantica.ontology` | SHACL, SKOS, alignments, diff/migration, auto-generation, OWL/RDF |
| `semantica.explorer` | FastAPI Knowledge Explorer, Ontology Hub, Distance Intelligence, SHACL Studio |
| `semantica.mcp_server` | MCP stdio server — 12 tools for Claude Desktop, VS Code, Cursor, Windsurf, Cline |
| `semantica.vector_store` | FAISS, Pinecone, Weaviate, Qdrant, Milvus, PgVector |
| `semantica.graph_store` | Neo4j, FalkorDB, Apache AGE, Amazon Neptune |
| `semantica.triplet_store` | In-memory and persistent RDF triple store with SPARQL |
| `semantica.ingest` | Files, web, feeds, databases, Snowflake, Parquet, XML, MCP |
| `semantica.parse` | Document parsing — PDF, DOCX, HTML, PPTX, Docling layout analysis |
| `semantica.split` | Text chunking — sentence, paragraph, token, semantic boundary strategies |
| `semantica.normalize` | Text normalization, entity canonicalization, whitespace and encoding cleanup |
| `semantica.embeddings` | Sentence-Transformers, FastEmbed, OpenAI, BGE, Ollama local embeddings |
| `semantica.pipeline` | Pipeline DSL, parallel workers, retry policies, failure handling |
| `semantica.export` | RDF, Parquet, ArangoDB AQL, CSV, OWL, Arrow, GraphML, GEXF, DOT |
| `semantica.visualization` | Programmatic graph rendering — force, hierarchical, circular, spring layouts |
| `semantica.deduplication` | Entity deduplication v1/v2, similarity scoring, blocking, merging |
| `semantica.conflicts` | Conflict detection and resolution across overlapping knowledge sources |
| `semantica.provenance` | W3C PROV-O lineage tracking, source attribution, audit trails |
| `semantica.change_management` | Version control with SHA-256 checksums, diff, rollback |
| `semantica.llms` | Groq, OpenAI, Anthropic, Gemini, Ollama, DeepSeek, Novita AI, LiteLLM, HuggingFace |
| `semantica.seed` | Foundation graph seeding from CSV, JSON, SQL, API, and RDF sources |
| `semantica.evals` | Evaluation harness — KG quality, extraction F1, pipeline benchmarking, regression tracking |
| `semantica.core` | Orchestration, ConfigManager, LifecycleManager, PluginRegistry, MethodRegistry |
| `semantica.utils` | Logging, validation, progress tracking, hash utilities, nested dict helpers |

## Built for High-Stakes Domains

Where every decision must be accountable and mistakes have real consequences:

<CardGroup cols={2}>
  <Card title="Healthcare & Life Sciences" icon="heart-pulse">
    Clinical decision support, drug interaction graphs, patient safety audit trails, HIPAA compliance.
  </Card>
  <Card title="Finance & Risk" icon="chart-line">
    Fraud detection graphs, SOX/GDPR/MiFID II compliance, risk assessment trails.
  </Card>
  <Card title="Legal & Compliance" icon="scale-balanced">
    Evidence-backed research, contract analysis, regulatory change tracking.
  </Card>
  <Card title="Cybersecurity" icon="shield">
    Threat attribution graphs, incident response timelines, security audit trails.
  </Card>
  <Card title="Government & Defense" icon="building-columns">
    Policy decision trails, classified information handling, provenance chains.
  </Card>
  <Card title="Critical Infrastructure" icon="bolt">
    Power grids, transportation safety, emergency response coordination.
  </Card>
</CardGroup>

## Why Semantica?

<CardGroup cols={3}>
  <Card title="Open Source, MIT" icon="code-branch">
    No vendor lock-in, no paywalled features. Every line of code is available and forkable.
  </Card>
  <Card title="Production Ready" icon="circle-check">
    1,000+ passing tests, `PipelineValidator`, `FailureHandler` with exponential backoff, 12 security fixes in v0.5.0.
  </Card>
  <Card title="Modular by Design" icon="puzzle-piece">
    Import only what you need. Use `NERExtractor` without a graph store. Every component is independently swappable.
  </Card>
</CardGroup>
