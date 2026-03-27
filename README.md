<div align="center">

<img src="Semantica Logo.png" alt="Semantica Logo" width="420"/>

# 🧠 Semantica

**A Framework for Building Context Graphs and Decision Intelligence Layers for AI**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/semantica.svg)](https://pypi.org/project/semantica/)
[![Version](https://img.shields.io/badge/version-0.3.0-brightgreen.svg)](https://github.com/Hawksight-AI/semantica/releases/tag/v0.3.0)
[![Total Downloads](https://static.pepy.tech/badge/semantica)](https://pepy.tech/project/semantica)
[![CI](https://github.com/Hawksight-AI/semantica/workflows/CI/badge.svg)](https://github.com/Hawksight-AI/semantica/actions)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/sV34vps5hH)
[![X](https://img.shields.io/badge/X-Follow-black?logo=x&logoColor=white)](https://x.com/BuildSemantica)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2?logo=discord&logoColor=white)](https://discord.gg/sV34vps5hH)
[![X](https://img.shields.io/badge/X-Follow%20Semantica-black?logo=x&logoColor=white)](https://x.com/BuildSemantica)

### ⭐ Give us a Star • 🍴 Fork us • 💬 Join our Discord • 🐦 Follow on X

> **Transform Chaos into Intelligence. Build AI systems with context graphs, decision tracking, and advanced knowledge engineering that are explainable, traceable, and trustworthy — not black boxes.**

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

## The Solution

Semantica is the **context and intelligence layer** you add to your AI stack:

- **Context Graphs** — structured graph of entities, relationships, and decisions your agent builds as it works. Queryable, traceable, persistent.
- **Decision Intelligence** — every decision is a first-class object: recorded, linked causally, searchable by precedent, and analyzable for downstream impact.
- **Provenance** — every fact links to its source. W3C PROV-O compliant. Full lineage from ingestion to inference.
- **Reasoning engines** — forward chaining, Rete networks, deductive, abductive, and SPARQL reasoning. Explainable inference paths, not black-box answers.
- **Deduplication & QA** — conflict detection, entity resolution, and validation built into the pipeline.

Works alongside LangChain, LlamaIndex, AutoGen, CrewAI, and any LLM provider — Semantica is not a replacement, it's the accountability layer on top.

### ⚡ Quick Installation

```bash
pip install semantica
```

---

## What's New in v0.3.0

> First stable release — `Production/Stable` on PyPI. Ships across three stages: 0.3.0-alpha, 0.3.0-beta, and 0.3.0 stable.

| Area | Highlights |
|------|-----------|
| **Context Graphs** | Temporal validity windows (`valid_from`/`valid_until`), weighted BFS (`min_weight`), cross-graph navigation (`link_graph`, `navigate_to`, `resolve_links`) with full save/load persistence |
| **Decision Intelligence** | Complete lifecycle: `record_decision` → `trace_decision_chain` → `analyze_decision_impact` → `find_similar_decisions`; hybrid precedent search; `PolicyEngine` with versioned rules |
| **KG Algorithms** | PageRank, betweenness, community detection (Louvain), Node2Vec embeddings, link prediction, path finding — all returning structured dicts |
| **Semantic Extraction** | LLM relation extraction fixed (no silent drops); `_match_pattern` rewritten; duplicate relation bug removed; `"llm_typed"` metadata corrected |
| **Deduplication v2** | `blocking_v2`/`hybrid_v2` candidate generation (**63.6% faster**); two-stage prefilter (**18–25% faster**); semantic dedup v2 (**6.98x faster**) |
| **Delta Processing** | SPARQL-based incremental diff; `delta_mode` pipelines; snapshot versioning with `prune_versions()` |
| **Export** | RDF format aliases (`"ttl"`, `"json-ld"`, etc.); ArangoDB AQL export; Apache Parquet export (Spark/BigQuery/Databricks ready) |
| **Pipeline** | `FailureHandler` with LINEAR/EXPONENTIAL/FIXED backoff; `PipelineValidator` returning `ValidationResult`; retry loop fixed |
| **Graph Backends** | Apache AGE (SQL injection fixed), AWS Neptune, FalkorDB, PgVector (HNSW/IVFFlat indexing) |
| **Tests** | **886+ passing, 0 failures** — 335 context, ~430 KG, 70 semantic extraction, 85 real-world E2E |

See [RELEASE_NOTES.md](RELEASE_NOTES.md) for the full per-contributor breakdown and [CHANGELOG](CHANGELOG.md) for the complete diff.

---

## Unreleased / Coming Next

| Area | Highlights |
|------|-----------|
| **SHACL Constraints** | `OntologyEngine.to_shacl()` auto-derives SHACL shapes from any OWL ontology; `validate_graph()` returns structured `SHACLValidationReport` with plain-English violation explanations; three quality tiers (`"basic"`, `"standard"`, `"strict"`); three output formats (Turtle, JSON-LD, N-Triples); 3-level inheritance propagation |

---

## Features

### Context & Decision Intelligence
- **Context Graphs** — structured graph of entities, relationships, and decisions; queryable, causal, persistent
- **Decision tracking** — record, link, and analyze every agent decision with `add_decision()`, `record_decision()`
- **Causal chains** — link decisions with `add_causal_relationship()`, trace lineage with `trace_decision_chain()`
- **Precedent search** — hybrid similarity search over past decisions with `find_similar_decisions()`
- **Influence analysis** — `analyze_decision_impact()`, `analyze_decision_influence()` — understand downstream effects
- **Policy engine** — enforce business rules with `check_decision_rules()`; automated compliance validation
- **Agent memory** — `AgentMemory` with short/long-term storage, conversation history, and statistics
- **Cross-system context capture** — `capture_cross_system_inputs()` for multi-agent pipelines

### Knowledge Graphs
- **Knowledge graph construction** — entities, relationships, properties, typed edges
- **Graph algorithms** — PageRank, betweenness centrality, clustering coefficient, community detection
- **Node embeddings** — Node2Vec embeddings via `NodeEmbedder`
- **Similarity** — cosine similarity via `SimilarityCalculator`
- **Link prediction** — score potential new edges via `LinkPredictor`
- **Temporal graphs** — time-aware nodes and edges
- **Incremental / delta processing** — update graphs without full recompute

### Semantic Extraction
- **Entity extraction** — named entity recognition, normalization, classification
- **Relation extraction** — triplet generation from raw text using LLMs or rule-based methods
- **LLM-typed extraction** — extraction with typed relation metadata
- **Deduplication v1** — Jaro-Winkler similarity, basic blocking
- **Deduplication v2** — `blocking_v2`, `hybrid_v2`, `semantic_v2` strategies with `max_candidates_per_entity`
- **Triplet deduplication** — `dedup_triplets()` for removing duplicate (subject, predicate, object) triples

### Reasoning Engines
- **Forward chaining** — `Reasoner` with IF/THEN string rules and dict facts
- **Rete network** — `ReteEngine` for high-throughput production rule matching
- **Deductive reasoning** — `DeductiveReasoner` for classical inference
- **Abductive reasoning** — `AbductiveReasoner` for hypothesis generation from observations
- **SPARQL reasoning** — `SPARQLReasoner` for query-based inference over RDF graphs

### Provenance & Auditability
- **Entity provenance** — `ProvenanceTracker.track_entity(id, source_url, metadata)`
- **Algorithm provenance** — `AlgorithmTrackerWithProvenance` tracks computation lineage
- **Graph builder provenance** — `GraphBuilderWithProvenance` records entity source lineage from URLs
- **W3C PROV-O compliant** — lineage tracking across all modules
- **Change management** — version control with checksums, audit trails, compliance support

### Vector Store
- **Backends** — FAISS, Pinecone, Weaviate, Qdrant, Milvus, PgVector, in-memory
- **Semantic search** — top-k retrieval by embedding similarity
- **Hybrid search** — vector + keyword with configurable weights
- **Filtered search** — metadata-based filtering on any field
- **Custom similarity weights** — tune retrieval per use case

### 🌐 Graph Database Support
- **AWS Neptune** — Amazon Neptune graph database with IAM authentication
- **Apache AGE** — PostgreSQL graph extension with openCypher via SQL
- **FalkorDB** — native support; `DecisionQuery` and `CausalChainAnalyzer` work directly with FalkorDB row/header shapes

### Data Ingestion
- **File formats** — PDF, DOCX, HTML, JSON, CSV, Excel, PPTX, archives
- **Web crawl** — `WebIngestor` with configurable depth
- **Databases** — `DBIngestor` with SQL query support
- **Snowflake** — `SnowflakeIngestor` with table/query ingestion, pagination, and key-pair/OAuth auth
- **Docling** — advanced document parsing with table and layout extraction (PDF, DOCX, PPTX, XLSX)
- **Media** — image OCR, audio/video metadata extraction

### Export Formats
- **RDF** — Turtle (`.ttl`), JSON-LD, N-Triples (`.nt`), XML via `RDFExporter`
- **Parquet** — `ParquetExporter` for entities, relationships, and full KG export
- **ArangoDB AQL** — ready-to-run INSERT statements via `ArangoAQLExporter`
- **OWL ontologies** — export generated ontologies in Turtle or RDF/XML
- **SHACL shapes** — export auto-derived constraint shapes via `RDFExporter.export_shacl()` (`.ttl`, `.jsonld`, `.nt`, `.shacl`)

### Pipeline & Production
- **Pipeline builder** — `PipelineBuilder` with stage chaining and parallel workers
- **Validation** — `PipelineValidator` returns `ValidationResult(valid, errors, warnings)` before execution
- **Failure handling** — `FailureHandler` with `RetryPolicy` and `RetryStrategy` (exponential backoff, fixed, etc.)
- **Parallel processing** — configurable worker count per pipeline stage
- **LLM providers** — 100+ models via LiteLLM (OpenAI, Anthropic, Cohere, Mistral, Ollama, and more)

### Ontology
- **Auto-generation** — derive OWL ontologies from knowledge graphs via `OntologyGenerator`
- **Import** — load existing OWL, RDF, Turtle, JSON-LD ontologies via `OntologyImporter`
- **Validation** — HermiT/Pellet compatible consistency checking
- **SHACL shape generation** — `OntologyEngine.to_shacl()` auto-derives SHACL node and property shapes from any Semantica ontology dict; zero hand-authoring; deterministic (same ontology → same shapes)
- **SHACL validation** — `OntologyEngine.validate_graph()` runs shapes against a data graph and returns a `SHACLValidationReport` with machine-readable violations and plain-English explanations
- **Quality tiers** — `"basic"` (structure + cardinality), `"standard"` (+ enumerations, inheritance), `"strict"` (+ `sh:closed` rejects undeclared properties)
- **Inheritance propagation** — child shapes automatically include all ancestor property shapes (up to 3+ levels), cycle-safe
- **Three output formats** — Turtle (`.ttl`), JSON-LD, N-Triples; file export via `export_shacl()`

---

## Modules

| Module | What it provides |
|---|---|
| `semantica.context` | Context graphs, agent memory, decision tracking, causal analysis, precedent search, policy engine |
| `semantica.kg` | Knowledge graph construction, graph algorithms, centrality, community detection, embeddings, link prediction, provenance |
| `semantica.semantic_extract` | NER, relation extraction, event extraction, coreference, triplet generation, LLM-enhanced extraction |
| `semantica.reasoning` | Forward chaining, Rete network, deductive, abductive, SPARQL reasoning, explanation generation |
| `semantica.vector_store` | FAISS, Pinecone, Weaviate, Qdrant, Milvus, PgVector, in-memory; hybrid & filtered search |
| `semantica.export` | RDF (Turtle/JSON-LD/N-Triples/XML), Parquet, ArangoDB AQL, CSV, YAML, OWL, graph formats |
| `semantica.ingest` | Files (PDF, DOCX, CSV, HTML), web crawl, feeds, databases, Snowflake, MCP, email, repositories |
| `semantica.ontology` | Auto-generation (6-stage pipeline), OWL/RDF export, import (OWL/RDF/Turtle/JSON-LD), validation, versioning, **SHACL shape generation & validation** |
| `semantica.pipeline` | Pipeline DSL, parallel workers, validation, retry policies, failure handling, resource scheduling |
| `semantica.graph_store` | Graph database backends — Neo4j, FalkorDB, Apache AGE, Amazon Neptune; Cypher queries |
| `semantica.embeddings` | Text embedding generation — Sentence-Transformers, FastEmbed, OpenAI, BGE; similarity calculation |
| `semantica.deduplication` | Entity deduplication, similarity scoring, merging, clustering; blocking and semantic strategies |
| `semantica.provenance` | W3C PROV-O compliant end-to-end lineage tracking, source attribution, audit trails |
| `semantica.parse` | Document parsing — PDF, DOCX, PPTX, HTML, code, email, structured data, media with OCR |
| `semantica.split` | Document chunking — recursive, semantic, entity-aware, relation-aware, graph-based, ontology-aware |
| `semantica.normalize` | Data normalization for text, entities, dates, numbers, quantities, languages, encodings |
| `semantica.conflicts` | Multi-source conflict detection (value, type, relationship, temporal, logical) with resolution strategies |
| `semantica.change_management` | Version storage, change tracking, checksums, audit trails, compliance support for KGs and ontologies |
| `semantica.triplet_store` | RDF triplet store integration — Blazegraph, Jena, RDF4J; SPARQL queries and bulk loading |
| `semantica.visualization` | Interactive and static visualization of KGs, ontologies, embeddings, analytics, and temporal graphs |
| `semantica.seed` | Seed data management for initial KG construction from CSV, JSON, databases, and APIs |
| `semantica.core` | Framework orchestration, configuration management, knowledge base construction, plugin system |
| `semantica.llms` | LLM provider integrations — Groq, OpenAI, Novita AI, HuggingFace, LiteLLM |
| `semantica.utils` | Shared utilities — logging, validation, exception handling, constants, types, progress tracking |

---

## ⚡ Quick Start

```python
import semantica
from semantica.context import AgentContext, ContextGraph
from semantica.vector_store import VectorStore

# Build an agent with structured context
context = AgentContext(
    vector_store=VectorStore(backend="faiss", dimension=768),
    knowledge_graph=ContextGraph(advanced_analytics=True),
    decision_tracking=True,
    kg_algorithms=True,
)

# Store memory
memory_id = context.store(
    "GPT-4 outperforms GPT-3.5 on reasoning benchmarks by 40%",
    conversation_id="research_session_1",
)

# Record a decision with full context
decision_id = context.record_decision(
    category="model_selection",
    scenario="Choose LLM for production reasoning pipeline",
    reasoning="GPT-4 benchmark advantage justifies 3x cost increase",
    outcome="selected_gpt4",
    confidence=0.91,
    entities=["gpt4", "gpt35", "reasoning_pipeline"],
)

# Find similar decisions from history
precedents = context.find_precedents("model selection reasoning", limit=5)

# Analyze downstream influence of this decision
influence = context.analyze_decision_influence(decision_id)
```

**[📖 Full Quick Start](#-quick-start)** • **[🍳 Cookbook Examples](#-semantica-cookbook)** • **[💬 Join Discord](https://discord.gg/sV34vps5hH)** • **[⭐ Star Us](https://github.com/Hawksight-AI/semantica)**

---

## Core Value Proposition

| **Trustworthy** | **Explainable** | **Auditable** |
|:------------------:|:------------------:|:-----------------:|
| Conflict detection & validation | Transparent reasoning paths | Complete provenance tracking |
| Rule-based governance | Entity relationships & ontologies | W3C PROV-O compliant lineage |
| Production-grade QA | Multi-hop graph reasoning | Source tracking & integrity verification |

---

## Key Features & Benefits

### Not Just Another Agentic Framework

**Semantica complements** LangChain, LlamaIndex, AutoGen, CrewAI, Google ADK, Agno, and other frameworks to enhance your agents with:

| Feature | Benefit |
|:--------|:--------|
| **Context Graphs** | Structured knowledge representation with entity relationships and semantic context |
| **Decision Tracking** | Complete decision lifecycle management with precedent search and causal analysis |
| **KG Algorithms** | Advanced graph analytics including centrality, community detection, and embeddings |
| **Vector Store Integration** | Hybrid search with custom similarity weights and advanced filtering |
| **Auditable** | Complete provenance tracking with W3C PROV-O compliance |
| **Explainable** | Transparent reasoning paths with entity relationships |
| **Provenance-Aware** | End-to-end lineage from documents to responses |
| **Validated** | Built-in conflict detection, deduplication, QA |
| **Governed** | Rule-based validation and semantic consistency |
| **Version Control** | Enterprise-grade change management with integrity verification |

### Perfect For High-Stakes Use Cases

| 🏥 **Healthcare** | 💰 **Finance** | ⚖️ **Legal** |
|:-----------------:|:--------------:|:------------:|
| Clinical decisions | Fraud detection | Evidence-backed research |
| Drug interactions | Regulatory support | Contract analysis |
| Patient safety | Risk assessment | Case law reasoning |

| 🔒 **Cybersecurity** | 🏛️ **Government** | 🏭 **Infrastructure** | 🚗 **Autonomous** |
|:-------------------:|:----------------:|:-------------------:|:-----------------:|
| Threat attribution | Policy decisions | Power grids | Decision logs |
| Incident response | Classified info | Transportation | Safety validation |

### Powers Your AI Stack

- **Context Graphs** — Structured knowledge representation with entity relationships and semantic context
- **Decision Tracking Systems** — Complete decision lifecycle management with precedent search and causal analysis
- **GraphRAG Systems** — Retrieval with graph reasoning and hybrid search using KG algorithms
- **AI Agents** — Trustworthy, accountable multi-agent systems with semantic memory and decision history
- **Reasoning Models** — Explainable AI decisions with reasoning paths and influence analysis
- **Enterprise AI** — Governed, auditable platforms that support compliance and policy enforcement

### Integrations

- **Docling Support** — Document parsing with table extraction (PDF, DOCX, PPTX, XLSX)
- **AWS Neptune** — Amazon Neptune graph database support with IAM authentication
- **Apache AGE** — PostgreSQL graph extension backend (openCypher via SQL)
- **Snowflake** — Native ingestion with `SnowflakeIngestor`; table/query ingestion, pagination, key-pair & OAuth auth
- **Custom Ontology Import** — Import existing ontologies (OWL, RDF, Turtle, JSON-LD)

> **Built for environments where every answer must be explainable and governed.**

---

## Context Graphs & Decision Tracking

Semantica's flagship module. Tracks every decision your agent makes as a structured graph node — with causal links, precedent search, impact analysis, and policy enforcement.

```python
from semantica.context import ContextGraph

graph = ContextGraph(advanced_analytics=True)

# Record a loan approval decision
loan_id = graph.add_decision(
    category="loan_approval",
    scenario="Mortgage application — 780 credit score, 28% DTI",
    reasoning="Strong credit history, stable income for 8 years, low DTI",
    outcome="approved",
    confidence=0.95,
)

# Record a downstream dependent decision
rate_id = graph.add_decision(
    category="interest_rate",
    scenario="Set rate for approved mortgage",
    reasoning="Prime applicant qualifies for lowest tier rate",
    outcome="rate_set_6.2pct",
    confidence=0.98,
)

# Link the decisions causally
graph.add_causal_relationship(loan_id, rate_id, relationship_type="enables")

# Find similar past decisions using hybrid similarity
similar    = graph.find_similar_decisions("mortgage approval", max_results=5)
chain      = graph.trace_decision_chain(loan_id)
impact     = graph.analyze_decision_impact(loan_id)
compliance = graph.check_decision_rules({"category": "loan_approval", "confidence": 0.95})
insights   = graph.get_decision_insights()
```

```python
from semantica.context import AgentContext, AgentMemory
from semantica.vector_store import VectorStore

context = AgentContext(
    vector_store=VectorStore(backend="faiss", dimension=768),
    knowledge_graph=ContextGraph(advanced_analytics=True),
    decision_tracking=True,
    graph_expansion=True,
    kg_algorithms=True,
)

context.store("Regulation EU 2024/1689 requires explainability for high-risk AI", conversation_id="compliance_review")
context.store("Our fraud model flags 0.3% of transactions", conversation_id="compliance_review")

results = context.retrieve("AI regulation explainability requirements", limit=3)
history = context.get_conversation_history("compliance_review")
stats   = context.get_statistics()
```

---

## Knowledge Graphs

```python
from semantica.kg import KnowledgeGraph, Entity, Relationship
from semantica.kg import CentralityAnalyzer, NodeEmbedder, LinkPredictor

kg = KnowledgeGraph()

kg.add_entity(Entity(id="transformer", label="Transformer", type="Architecture",
                     properties={"year": 2017, "paper": "Attention Is All You Need"}))
kg.add_entity(Entity(id="bert", label="BERT", type="Model",
                     properties={"year": 2018, "parameters": "340M"}))
kg.add_entity(Entity(id="gpt4", label="GPT-4", type="Model", properties={"year": 2023}))

kg.add_relationship(Relationship(source="bert", target="transformer", type="based_on"))
kg.add_relationship(Relationship(source="gpt4", target="transformer", type="based_on"))

# Graph algorithms
analyzer    = CentralityAnalyzer(kg)
centrality  = analyzer.compute_pagerank()
betweenness = analyzer.compute_betweenness()

# Node embeddings (Node2Vec)
embedder   = NodeEmbedder()
embeddings = embedder.compute_embeddings(kg, node_labels=["Model"], relationship_types=["based_on"])

# Link prediction
predictor = LinkPredictor()
score     = predictor.score_link(kg, "gpt4", "bert", method="common_neighbors")

models      = kg.find_nodes(type="Model")
descendants = kg.get_neighbors("transformer", direction="incoming")
```

---

## Semantic Extraction

```python
from semantica.semantic_extract import extract_entities, extract_relations, extract_triplets

text = """
OpenAI released GPT-4 in March 2023. Microsoft integrated GPT-4 into Azure OpenAI Service.
Anthropic, founded by former OpenAI researchers, released Claude as a competing model.
"""

entities = extract_entities(text)
# → [Entity(label="OpenAI", type="Organization"), Entity(label="GPT-4", type="Model"), ...]

relations = extract_relations(text)
# → [Relation(source="OpenAI", type="released", target="GPT-4"), ...]

triplets = extract_triplets(text)
```

```python
from semantica.deduplication import DuplicateDetector

entities = [
    {"id": "e1", "name": "OpenAI Inc.", "type": "Organization"},
    {"id": "e2", "name": "Open AI",    "type": "Organization"},
    {"id": "e3", "name": "Anthropic",  "type": "Organization"},
]

detector   = DuplicateDetector()
duplicates = detector.detect_duplicates(entities, threshold=0.85)
# → [("e1", "e2")]

duplicates_v2 = detector.detect_duplicates(entities, threshold=0.85, strategy="semantic_v2")
```

---

## Reasoning Engines

```python
from semantica.reasoning import Reasoner

reasoner = Reasoner()
reasoner.add_rule("IF Person(?x) THEN Mortal(?x)")
reasoner.add_rule("IF Employee(?x) AND WorksAt(?x, ?y) THEN HasEmployer(?x, ?y)")

results = reasoner.infer_facts([
    "Person(Socrates)",
    "Employee(Alice)",
    {"source_name": "Alice", "target_name": "OpenAI", "type": "WorksAt"},
])
# → ["Mortal(Socrates)", "HasEmployer(Alice, OpenAI)"]
```

```python
from semantica.reasoning import ReteEngine

rete = ReteEngine()
rete.add_rule({
    "name": "flag_high_risk_transaction",
    "conditions": [
        {"field": "amount",  "operator": ">",  "value": 10000},
        {"field": "country", "operator": "in", "value": ["IR", "KP", "SY"]},
    ],
    "action": "flag_for_compliance_review",
})
matches = rete.match({"amount": 15000, "country": "IR", "id": "txn_9921"})
```

```python
from semantica.reasoning import DeductiveReasoner, AbductiveReasoner

deductive = DeductiveReasoner()
deductive.add_axiom("All transformers use attention mechanisms")
deductive.add_fact("BERT is a transformer")
conclusion = deductive.reason("Does BERT use attention?")

abductive = AbductiveReasoner()
abductive.add_observation("The model accuracy dropped 12% after deployment")
hypotheses = abductive.generate_hypotheses()
# → ["Distribution shift in production data", "Preprocessing pipeline mismatch", ...]
```

---

## Provenance Tracking

W3C PROV-O compliant lineage tracking. Every fact traces back to its origin.

```python
from semantica.kg import ProvenanceTracker, AlgorithmTrackerWithProvenance

tracker = ProvenanceTracker()
tracker.track_entity("gpt4_benchmark",
    source_url="https://openai.com/research/gpt-4",
    metadata={"metric": "MMLU", "score": 86.4})

algo_tracker = AlgorithmTrackerWithProvenance(provenance=True)
algo_tracker.track_graph_construction(
    algorithm="node2vec",
    input_data={"nodes": 1500, "edges": 4200},
    parameters={"dimensions": 128, "walk_length": 80},
)

sources      = tracker.get_all_sources("gpt4_benchmark")
all_entities = tracker.get_all_entities()
```

---

## Vector Store & Hybrid Search

```python
from semantica.vector_store import VectorStore

vs = VectorStore(backend="faiss", dimension=768)

vs.store("The Transformer architecture revolutionized NLP",
         metadata={"source": "arxiv", "year": 2017}, id="doc_001")
vs.store("BERT introduced bidirectional pre-training for language understanding",
         metadata={"source": "arxiv", "year": 2018}, id="doc_002")

results = vs.search("attention mechanisms in language models", top_k=5)

results = vs.hybrid_search(
    query="transformer pre-training",
    top_k=10,
    vector_weight=0.6,
    keyword_weight=0.4,
)

results = vs.search("pre-training", top_k=5, filter={"year": 2018})
```

---

## Data Ingestion

```python
from semantica.ingest import FileIngestor, WebIngestor, DBIngestor

file_ingestor = FileIngestor(recursive=True)
docs = file_ingestor.ingest("./research_papers/")

web_ingestor = WebIngestor(max_depth=2)
web_docs = web_ingestor.ingest("https://arxiv.org/abs/1706.03762")

db_ingestor = DBIngestor(connection_string="postgresql://user:pass@localhost/kg_db")
db_docs = db_ingestor.ingest(query="SELECT title, abstract FROM papers WHERE year >= 2020")

all_sources = docs + web_docs + db_docs
```

```python
from semantica.parse import DoclingParser

# Advanced table and layout extraction
docling = DoclingParser()
parsed  = docling.parse("financial_report.pdf")
```

```python
from semantica.ingest import SnowflakeIngestor

# Connect to Snowflake and ingest a table
ingestor = SnowflakeIngestor(
    account="myorg-myaccount",
    user="analyst",
    password="...",
    warehouse="COMPUTE_WH",
    database="ANALYTICS",
    schema="PUBLIC",
)

# Ingest a table with optional filtering and pagination
data = ingestor.ingest_table(
    table_name="customer_events",
    where="event_date >= '2024-01-01'",
    limit=10000,
)

# Or run a custom SQL query
data = ingestor.ingest_query(
    query="SELECT id, content, tags FROM knowledge_base WHERE active = TRUE",
    batch_size=500,
)

# Convert to Semantica documents for downstream pipeline use
docs = ingestor.export_as_documents(data, id_field="id", text_fields=["content"])

# Key-pair and OAuth auth are also supported via env vars:
# SNOWFLAKE_PRIVATE_KEY_PATH, SNOWFLAKE_TOKEN, SNOWFLAKE_AUTHENTICATOR
```

---

## Export

```python
from semantica.export import RDFExporter, ParquetExporter, ArangoAQLExporter

rdf_exporter = RDFExporter()
turtle   = rdf_exporter.export_to_rdf(kg, format="turtle")
jsonld   = rdf_exporter.export_to_rdf(kg, format="json-ld")
ntriples = rdf_exporter.export_to_rdf(kg, format="nt")

parquet_exporter = ParquetExporter()
parquet_exporter.export_entities(kg,        path="output/entities.parquet")
parquet_exporter.export_relationships(kg,   path="output/relationships.parquet")
parquet_exporter.export_knowledge_graph(kg, path="output/")

aql_exporter = ArangoAQLExporter()
aql_exporter.export(kg, path="output/insert.aql")
```

---

## Pipeline Orchestration

```python
from semantica.pipeline import PipelineBuilder, PipelineValidator, FailureHandler
from semantica.pipeline import RetryPolicy, RetryStrategy

builder = (
    PipelineBuilder()
    .add_stage("ingest",      FileIngestor(recursive=True))
    .add_stage("extract",     extract_triplets)
    .add_stage("deduplicate", DuplicateDetector())
    .add_stage("build_kg",    KnowledgeGraph())
    .add_stage("export",      RDFExporter())
    .with_parallel_workers(4)
)

validator = PipelineValidator()
result    = validator.validate(builder)
if result.valid:
    pipeline = builder.build()
    pipeline.run(input_path="./documents/")

retry_policy = RetryPolicy(strategy=RetryStrategy.EXPONENTIAL_BACKOFF, max_retries=3)
handler = FailureHandler()
handler.handle_failure(error=last_error, policy=retry_policy, retry_count=1)
```

---

## Ontology

```python
from semantica.ontology import OntologyGenerator, OntologyImporter

generator = OntologyGenerator()
ontology  = generator.generate(kg)
generator.export(ontology, path="domain_ontology.owl", format="turtle")

importer = OntologyImporter()
ontology = importer.load("existing_ontology.owl")
ontology = importer.load("schema.ttl", format="turtle")
ontology = importer.load("context.jsonld")
```

### SHACL Shape Generation & Validation

Semantica turns ontologies into executable data contracts. The constraints layer completes a hybrid reasoning system — symbolic constraints (SHACL) alongside semantic retrieval (embeddings).

**Phase 1 — Generate shapes from any ontology dict:**

```python
from semantica.ontology import OntologyEngine

engine   = OntologyEngine()
ontology = engine.from_data(data)          # or engine.from_text(...) / engine.to_owl(...)

# Generate SHACL shapes — zero hand-authoring
shacl_ttl  = engine.to_shacl(ontology)                        # Turtle string (default)
shacl_jld  = engine.to_shacl(ontology, format="json-ld")      # JSON-LD string
shacl_nt   = engine.to_shacl(ontology, format="n-triples")    # N-Triples string

# Write to file
engine.export_shacl(ontology, path="shapes/domain.ttl")
```

**Quality tiers — control constraint strictness:**

```python
# "basic"    — node shapes, property paths, datatypes, cardinality
# "standard" — + enumerations (sh:in), patterns, inheritance propagation  [DEFAULT]
# "strict"   — + sh:closed true on all shapes (rejects undeclared properties)

shacl = engine.to_shacl(ontology, quality_tier="strict")
```

**Phase 2 — Validate a graph against the shapes:**

```python
import pathlib

report = engine.validate_graph(
    data_graph=pathlib.Path("data/graph.ttl").read_text(),
    ontology=ontology,   # auto-generates SHACL before validating
    explain=True,        # populate plain-English explanations on each violation
)

print(report.summary())
# → "Graph does NOT conform: 2 violation(s)."

for v in report.violations:
    print(v.explanation)
# → "Node <https://example.com/john> is missing required property <ex:name>. At least 1 value(s) are required."
# → "Node <https://example.com/acme> has value '999' for <ex:employeeCount> but the expected datatype is xsd:string."

import json
print(json.dumps(report.to_dict(), indent=2))  # machine-readable — feed to LLM or pipeline
```

**Or validate against a pre-built SHACL file:**

```python
report = engine.validate_graph(
    data_graph=graph_turtle_string,
    shacl="shapes/domain.ttl",   # path or SHACL string
)
```

**Regenerate shapes in CI to detect breaking ontology changes:**

```bash
python -c "
from semantica.ontology import OntologyEngine
import json, pathlib
engine = OntologyEngine()
onto = engine.from_data(json.loads(pathlib.Path('ontology.json').read_text()))
engine.export_shacl(onto, 'shapes/shapes.ttl')
"
git diff shapes/shapes.ttl   # detects breaking ontology changes
```

> **Requires pyshacl for `validate_graph()`:** `pip install semantica[shacl]`
> Shape generation (`to_shacl`, `export_shacl`) works without any optional dependencies.

---

## Integrations

**Graph Databases**
- AWS Neptune — Amazon Neptune with IAM authentication
- Apache AGE — PostgreSQL + openCypher via SQL
- FalkorDB — native support for decision queries and causal analysis

**Vector Databases**
- FAISS — high-performance dense vector search
- Pinecone — serverless and pod-based managed vector database (`pip install semantica[vectorstore-pinecone]`)
- Weaviate — GraphQL-based vector store with rich schema management (`pip install semantica[vectorstore-weaviate]`)
- Qdrant — collection-based store with payload filtering (`pip install semantica[vectorstore-qdrant]`)
- Milvus — scalable store with partition support and multiple index types (`pip install semantica[vectorstore-milvus]`)
- PgVector — PostgreSQL pgvector extension with JSONB metadata (`pip install semantica[vectorstore-pgvector]`)
- In-memory — lightweight, zero-dependency store for development and testing

**Data Sources**
- Snowflake — `SnowflakeIngestor` for table/query ingestion, schema introspection, pagination, and multiple auth methods (password, key-pair, OAuth, SSO) (`pip install semantica[db-snowflake]`)

**Document Parsing**
- Docling — PDF, DOCX, PPTX, XLSX with table and layout extraction

**LLM Providers**
- 100+ models via LiteLLM — OpenAI, Anthropic, Cohere, Mistral, Ollama, Azure, AWS Bedrock, and more
- Novita AI — OpenAI-compatible provider (`deepseek/deepseek-v3.2` and more); configure via `NOVITA_API_KEY`

**Agentic Frameworks**
- Complements LangChain, LlamaIndex, AutoGen, CrewAI, Google ADK, and more

> **Agno — First-Class Integration** `pip install semantica[agno]`
>
> Semantica ships a dedicated Agno integration with five ready-to-use components:
> - **`AgnoContextStore`** — graph-backed agent memory
> - **`AgnoKnowledgeGraph`** — multi-hop GraphRAG knowledge base
> - **`AgnoDecisionKit`** — 6 decision-intelligence tools
> - **`AgnoKGToolkit`** — 7 knowledge-graph pipeline tools
> - **`AgnoSharedContext`** — shared context graph for multi-agent teams

**Export**
- RDF: Turtle, JSON-LD, N-Triples, XML · Parquet · ArangoDB AQL

---

## Installation

```bash
# Core
pip install semantica

# With all optional dependencies
pip install semantica[all]

# Vector store backends (install only what you need)
pip install semantica[vectorstore-pinecone]
pip install semantica[vectorstore-weaviate]
pip install semantica[vectorstore-qdrant]
pip install semantica[vectorstore-milvus]
pip install semantica[vectorstore-pgvector]

# SHACL validation (validate_graph)
pip install semantica[shacl]

# Snowflake ingestion
pip install semantica[db-snowflake]

# From source
git clone https://github.com/Hawksight-AI/semantica.git
cd semantica
pip install -e ".[dev]"

# Run tests
pytest tests/
```

---

## 🤝 Community & Support

### Join Our Community

| **Channel** | **Purpose** |
|:-----------:|:-----------|
| [**Discord**](https://discord.gg/sV34vps5hH) | Real-time help, showcases |
| [**GitHub Discussions**](https://github.com/Hawksight-AI/semantica/discussions) | Q&A, feature requests |

### Learning Resources


### Enterprise Support

Enterprise support, professional services, and commercial licensing will be available in the future. For now, we offer community support through Discord and GitHub Discussions.

**Current Support:**
- **Community Support** - Free support via [Discord](https://discord.gg/sV34vps5hH) and [GitHub Discussions](https://github.com/Hawksight-AI/semantica/discussions)
- **Bug Reports** - [GitHub Issues](https://github.com/Hawksight-AI/semantica/issues)

**Future Enterprise Offerings:**
- Professional support with SLA
- Enterprise licensing
- Custom development services
- Priority feature requests
- Dedicated support channels

Stay tuned for updates!

- **AI / ML engineers** — GraphRAG, explainable agents, decision tracing
- **Data engineers** — governed semantic pipelines with full provenance
- **Knowledge engineers** — ontology management and KG construction at scale
- **High-stakes domains** — healthcare, finance, legal, cybersecurity, government

---

## Resources

- [Documentation](https://github.com/Hawksight-AI/semantica/tree/main/docs)
- [Cookbook & Notebooks](https://github.com/Hawksight-AI/semantica/tree/main/cookbook)
- [Contributing Guide](CONTRIBUTING.md)
- [Changelog](https://github.com/Hawksight-AI/semantica/releases)
- [💬 Discord Community](https://discord.gg/sV34vps5hH)
- [Follow on X](https://x.com/BuildSemantica)

---

## Contributing

All contributions welcome — bug fixes, new features, tests, and docs.

1. Fork the repo and create a branch
2. `pip install -e ".[dev]"`
3. Write tests alongside your changes
4. Open a PR and tag `@KaifAhmad1` for review

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

---

<div align="center">

MIT License · Built by [Hawksight AI](https://github.com/Hawksight-AI) · [⭐ Star on GitHub](https://github.com/Hawksight-AI/semantica)

[GitHub](https://github.com/Hawksight-AI/semantica) • [Discord](https://discord.gg/sV34vps5hH)
