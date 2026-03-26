<div align="center">
  <img src="assets/img/Semantica Logo.png" alt="Semantica Logo" width="420" height="auto">

  <h1>🧠 Semantica</h1>

  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://pypi.org/project/semantica/"><img src="https://img.shields.io/pypi/v/semantica.svg" alt="PyPI"></a>
  <a href="https://github.com/Hawksight-AI/semantica/releases/tag/v0.3.0"><img src="https://img.shields.io/badge/version-0.3.0-brightgreen.svg" alt="Version"></a>
  <a href="https://pepy.tech/project/semantica"><img src="https://static.pepy.tech/badge/semantica" alt="Total Downloads"></a>
  <a href="https://github.com/Hawksight-AI/semantica/actions"><img src="https://github.com/Hawksight-AI/semantica/workflows/CI/badge.svg" alt="CI"></a>
  <a href="https://discord.gg/sV34vps5hH"><img src="https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://x.com/BuildSemantica"><img src="https://img.shields.io/badge/X-Follow-black?logo=x&logoColor=white" alt="X"></a>

  <p><strong>A Framework for Building Context Graphs and Decision Intelligence Layers for AI</strong></p>

  <p>⭐ Give us a Star &nbsp;•&nbsp; 🍴 Fork us &nbsp;•&nbsp; 💬 Join our Discord &nbsp;•&nbsp; 🐦 Follow on X</p>

  <p><em>Transform Chaos into Intelligence. Build AI systems with context graphs, decision tracking, and advanced knowledge engineering that are explainable, traceable, and trustworthy — not black boxes.</em></p>

  <p>
    <a href="getting-started/" class="md-button md-button--primary">Get Started</a>
    <a href="https://github.com/Hawksight-AI/semantica" class="md-button">View on GitHub</a>
  </p>
</div>

---

## The Problem

AI agents today are capable but not trustworthy:

- **No memory structure** — agents store embeddings, not meaning. Retrieval is fuzzy; there's no way to ask *why* something was recalled.
- **No decision trail** — agents make decisions continuously but record nothing. When something goes wrong, there's no history to debug or audit.
- **No provenance** — outputs cannot be traced back to source facts. In regulated industries, this is a compliance blocker.
- **No reasoning transparency** — black-box answers with no explanation of how a conclusion was reached.
- **No conflict detection** — contradictory facts silently coexist in vector stores, producing unpredictable answers.

These aren't edge cases. They are the reason AI cannot be deployed in healthcare, finance, legal, and government without custom guardrails built from scratch.

---

## The Solution

Semantica is the **context and intelligence layer** you add to your AI stack:

- **Context Graphs** — structured graph of entities, relationships, and decisions your agent builds as it works. Queryable, traceable, persistent.
- **Decision Intelligence** — every decision is a first-class object: recorded, linked causally, searchable by precedent, and analyzable for downstream impact.
- **Provenance** — every fact links to its source. W3C PROV-O compliant. Full lineage from ingestion to inference.
- **Reasoning engines** — forward chaining, Rete networks, deductive, abductive, and SPARQL reasoning. Explainable inference paths, not black-box answers.
- **Deduplication & QA** — conflict detection, entity resolution, and validation built into the pipeline.

Works alongside LangChain, LlamaIndex, AutoGen, CrewAI, and any LLM provider — Semantica is not a replacement, it's the accountability layer on top.

---

### ⚡ Quick Installation

```bash
pip install semantica
```

```python
from semantica.context import AgentContext, ContextGraph
from semantica.vector_store import VectorStore

context = AgentContext(
    vector_store=VectorStore(backend="faiss", dimension=768),
    knowledge_graph=ContextGraph(advanced_analytics=True),
    decision_tracking=True,
)

# Store a memory
context.store("GPT-4 outperforms GPT-3.5 on reasoning benchmarks by 40%")

# Record a decision
decision_id = context.record_decision(
    category="model_selection",
    scenario="Choose LLM for production reasoning pipeline",
    reasoning="GPT-4 benchmark advantage justifies 3x cost increase",
    outcome="selected_gpt4",
    confidence=0.91,
)

# Find similar past decisions and analyze downstream impact
precedents = context.find_precedents("model selection reasoning", limit=5)
influence  = context.analyze_decision_influence(decision_id)
```

**[Full Quick Start](getting-started.md)** &nbsp;•&nbsp; **[Cookbook](cookbook.md)** &nbsp;•&nbsp; **[Join Discord](https://discord.gg/sV34vps5hH)**

---

## What's New in v0.3.0

> First stable release (`Production/Stable` on PyPI).

| Area | Highlights |
|------|------------|
| **Context Graphs** | Temporal validity windows, weighted BFS, cross-graph navigation with save/load persistence |
| **Decision Intelligence** | Full lifecycle: record → trace → impact → precedent; `PolicyEngine` with versioned rules |
| **KG Algorithms** | PageRank, betweenness, Louvain community detection, Node2Vec, link prediction |
| **Semantic Extraction** | LLM extraction fixed (no silent drops), duplicate relation bug removed, `"llm_typed"` metadata corrected |
| **Deduplication v2** | `blocking_v2`/`hybrid_v2` — 63.6% faster; semantic v2 — 6.98x faster |
| **Delta Processing** | SPARQL-based incremental diff, `delta_mode` pipelines, snapshot versioning |
| **Export** | RDF aliases (`"ttl"`, `"json-ld"`), ArangoDB AQL, Apache Parquet (Spark/BigQuery/Databricks) |
| **Pipeline** | `FailureHandler` with LINEAR/EXPONENTIAL/FIXED backoff; `PipelineValidator` returning `ValidationResult` |
| **Graph Backends** | Apache AGE (SQL injection fixed), AWS Neptune, FalkorDB, PgVector (HNSW/IVFFlat) |
| **Tests** | 886+ passing, 0 failures — 335 context, ~430 KG, 70 semantic extraction, 85 real-world E2E |

---

## Core Value Proposition

| **Trustworthy** | **Explainable** | **Auditable** |
|:---:|:---:|:---:|
| Conflict detection & validation | Transparent reasoning paths | Complete provenance tracking |
| Rule-based governance | Entity relationships & ontologies | W3C PROV-O compliant lineage |
| Production-grade QA | Multi-hop graph reasoning | Source tracking & integrity verification |

---

## Features

### Context & Decision Intelligence
- **Context Graphs** — structured, persistent graph of entities, relationships, and decisions
- **Decision tracking** — `add_decision()`, `record_decision()` for full lifecycle management
- **Causal chains** — `add_causal_relationship()`, `trace_decision_chain()`
- **Precedent search** — hybrid similarity search over past decisions via `find_similar_decisions()`
- **Influence analysis** — `analyze_decision_impact()`, `analyze_decision_influence()`
- **Policy engine** — `check_decision_rules()` with versioned, automated compliance rules
- **Agent memory** — `AgentMemory` with short/long-term storage and conversation history

### Knowledge Graphs
- **Graph construction** — entities, relationships, properties, typed edges
- **Algorithms** — PageRank, betweenness centrality, clustering coefficient, community detection
- **Node embeddings** — Node2Vec via `NodeEmbedder`; cosine similarity via `SimilarityCalculator`
- **Link prediction** — score potential edges via `LinkPredictor`
- **Temporal graphs** — time-aware nodes and edges with validity windows
- **Delta processing** — incremental updates without full recompute

### Semantic Extraction
- **NER** — named entity recognition, normalization, classification
- **Relation extraction** — triplet generation via LLMs or rule-based methods, with `"llm_typed"` metadata
- **Deduplication v1/v2** — Jaro-Winkler, `blocking_v2`, `hybrid_v2`, `semantic_v2`; `dedup_triplets()` for triples

### Reasoning
- **Forward chaining** — `Reasoner` with IF/THEN string rules and dict facts
- **Rete network** — `ReteEngine` for high-throughput production rule matching
- **Deductive / Abductive** — `DeductiveReasoner`, `AbductiveReasoner`
- **SPARQL** — `SPARQLReasoner` for query-based inference over RDF graphs

### Provenance & Auditability
- **Entity provenance** — `ProvenanceTracker.track_entity()`
- **Algorithm provenance** — `AlgorithmTrackerWithProvenance`
- **W3C PROV-O compliant** — lineage tracking across all modules
- **Change management** — version control with checksums, audit trails, compliance support

### Vector Store
- **Backends** — FAISS, Pinecone, Weaviate, Qdrant, Milvus, PgVector, in-memory
- **Search modes** — semantic top-k, hybrid (vector + keyword), metadata-filtered

### Data Ingestion
- **Files** — PDF, DOCX, HTML, JSON, CSV, Excel, PPTX, archives
- **Sources** — web crawl, SQL databases, Snowflake, feeds, email, repositories
- **Docling** — advanced parsing with table and layout extraction
- **Media** — image OCR, audio/video metadata

### Export
- **RDF** — Turtle, JSON-LD, N-Triples, XML via `RDFExporter`
- **Parquet** — `ParquetExporter` for Spark/BigQuery/Databricks pipelines
- **ArangoDB AQL** — ready-to-run INSERT statements
- **OWL ontologies** — Turtle or RDF/XML

### Pipeline & Ontology
- **Pipeline DSL** — `PipelineBuilder` with stage chaining, parallel workers, retry policies
- **Ontology** — auto-generate OWL from KGs, import OWL/RDF/Turtle/JSON-LD, HermiT/Pellet validation

---

## Modules

| Module | What it provides |
|--------|-----------------|
| `semantica.context` | Context graphs, agent memory, decision tracking, causal analysis, precedent search, policy engine |
| `semantica.kg` | KG construction, graph algorithms, centrality, community detection, embeddings, link prediction |
| `semantica.semantic_extract` | NER, relation extraction, event extraction, coreference, triplet generation, LLM extraction |
| `semantica.reasoning` | Forward chaining, Rete network, deductive, abductive, SPARQL reasoning, explanation generation |
| `semantica.vector_store` | FAISS, Pinecone, Weaviate, Qdrant, Milvus, PgVector; hybrid & filtered search |
| `semantica.export` | RDF, Parquet, ArangoDB AQL, CSV, YAML, OWL, graph formats |
| `semantica.ingest` | Files, web crawl, feeds, databases, Snowflake, MCP, email, repositories |
| `semantica.ontology` | Auto-generation, OWL/RDF export, import, validation, versioning |
| `semantica.pipeline` | Pipeline DSL, parallel workers, validation, retry policies, failure handling |
| `semantica.graph_store` | Neo4j, FalkorDB, Apache AGE, Amazon Neptune; Cypher queries |
| `semantica.embeddings` | Sentence-Transformers, FastEmbed, OpenAI, BGE; similarity calculation |
| `semantica.deduplication` | Entity deduplication, similarity scoring, merging, clustering |
| `semantica.provenance` | W3C PROV-O lineage tracking, source attribution, audit trails |
| `semantica.parse` | PDF, DOCX, PPTX, HTML, code, email, structured data, OCR |
| `semantica.split` | Recursive, semantic, entity-aware, relation-aware, graph-based chunking |
| `semantica.normalize` | Text, entities, dates, numbers, quantities, languages, encodings |
| `semantica.conflicts` | Multi-source conflict detection (value, type, temporal, logical) with resolution |
| `semantica.change_management` | Version storage, change tracking, checksums, audit trails |
| `semantica.triplet_store` | Blazegraph, Jena, RDF4J; SPARQL queries and bulk loading |
| `semantica.visualization` | Interactive/static KG, ontology, embedding, and temporal graph visualization |
| `semantica.core` | Framework orchestration, configuration, plugin system |
| `semantica.llms` | Groq, OpenAI, Novita AI, HuggingFace, LiteLLM integrations |

---

## Built for High-Stakes Domains

Where **every decision must be accountable** and **mistakes have real consequences**:

- **🏥 Healthcare & Life Sciences** — Clinical decision support, drug interactions, patient safety
- **💰 Finance & Risk** — Fraud detection, SOX/GDPR/MiFID II compliance, risk assessment
- **⚖️ Legal & Compliance** — Evidence-backed research, contract analysis, regulatory tracking
- **🔒 Cybersecurity** — Threat attribution, incident response, security audit trails
- **🏛️ Government & Defense** — Policy decisions, classified information handling, defense intelligence
- **🏭 Critical Infrastructure** — Power grids, transportation safety, emergency response
- **🚗 Autonomous Systems** — Self-driving, robotics safety, industrial automation

---

## Choose Your Path

<div class="grid cards" markdown>

-   :material-rocket-launch: **Quick Start**
    ---
    Up and running in minutes.

    [:arrow_right: Start Here](getting-started.md)

-   :material-book-open-page-variant: **Core Concepts**
    ---
    Knowledge graphs, ontologies, and semantic reasoning explained.

    [:arrow_right: Learn Concepts](concepts.md)

-   :material-code-braces: **API Reference**
    ---
    Full technical documentation for every module and class.

    [:arrow_right: View API](reference/core.md)

-   :material-chef-hat: **Cookbook**
    ---
    14 domain-specific cookbooks with real-world examples.

    [:arrow_right: Explore Cookbook](cookbook.md)

</div>

---

## Installation

!!! success "Now Available on PyPI!"
    Install with a single command.

=== "PyPI (Recommended)"

    ```bash
    pip install semantica

    # With all optional dependencies
    pip install semantica[all]
    ```

=== "From Source"

    ```bash
    git clone https://github.com/Hawksight-AI/semantica.git
    cd semantica
    pip install -e .          # core
    pip install -e ".[all]"   # all extras
    ```

=== "Development"

    ```bash
    git clone https://github.com/Hawksight-AI/semantica.git
    cd semantica
    pip install -e ".[dev]"
    ```

=== "Docker"

    ```bash
    docker pull semantica/semantica:latest
    docker run -it semantica/semantica
    ```

---

## Why Semantica?

<div class="grid cards" markdown>

-   **🆓 Open Source**
    ---
    MIT licensed. No vendor lock-in.

-   **🚀 Production Ready**
    ---
    Battle-tested with QA, conflict resolution, and validation built in.

-   **🧩 Modular**
    ---
    Use only what you need. Swap components easily.

-   **🌍 Community Driven**
    ---
    Built by developers, for developers. Active Discord.

-   **📚 End-to-End**
    ---
    From ingestion to reasoning — no duct-taping required.

-   **🔬 Research-Backed**
    ---
    Grounded in knowledge graph, ontology, and semantic web research.

</div>

---

## Learn More

- [Getting Started](getting-started.md) — your first knowledge graph in 5 minutes
- [Core Concepts](concepts.md) — knowledge graphs, ontologies, and semantic reasoning
- [Cookbook](cookbook.md) — 14 domain-specific cookbooks with Jupyter notebooks
- [API Reference](reference/core.md) — complete technical documentation
