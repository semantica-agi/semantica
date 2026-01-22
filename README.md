<div align="center">

<img src="semantica_logo.png" alt="Semantica Logo" width="460"/>

# 🧠 Semantica
### Open-Source Semantic Layer & Knowledge Engineering Framework

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/semantica.svg)](https://pypi.org/project/semantica/)
[![Monthly Downloads](https://img.shields.io/pypi/dm/semantica)](https://pypi.org/project/semantica/)
[![Total Downloads](https://static.pepy.tech/badge/semantica)](https://pepy.tech/project/semantica)
[![CI](https://github.com/Hawksight-AI/semantica/workflows/CI/badge.svg)](https://github.com/Hawksight-AI/semantica/actions)
[![Discord](https://img.shields.io/badge/Discord-Join-7289da?logo=discord&logoColor=white)](https://discord.gg/pMHguUzG)

### ⭐ Give us a Star • 🍴 Fork us • 💬 Join our Discord

> **Transform Choas into Intelligent Knowledge. Build AI systems that are explainable, traceable, and trustworthy — not black boxes.**

</div>

---

## 🔍 What is Semantica?

**Semantica** is an **open-source semantic intelligence framework** that transforms raw, unstructured data into **validated, explainable, and auditable knowledge** for modern AI systems.

It provides the **semantic foundation** for:
- **GraphRAG systems**
- **AI Agents & Multi-Agent Systems**
- **Reasoning and decision-support models**
- **High-stakes enterprise AI platforms**

Semantica is built for environments where **every answer must be explainable, traceable, and governed**.

👉 **If you care about trustworthy AI, semantic reasoning, or GraphRAG — please ⭐ star the repo, 🍴 fork it, and 💬 join our Discord.**

---

## 🚨 The Core Problem: The Semantic & Trust Gap

Most AI systems fail in high-stakes domains because they operate on **text similarity**, not **meaning**.

### What Organizations Have
- PDFs, DOCX, emails, logs
- APIs, databases, streams
- Conflicting facts and duplicates
- Siloed systems with no lineage

### What High-Stakes AI Requires
- Formal domain rules (ontologies)
- Structured and validated entities
- Explicit semantic relationships
- **Explainable reasoning paths**
- **End-to-end traceability**
- **Audit-ready provenance**

Without semantics:
- ❌ Decisions cannot be explained
- ❌ Errors cannot be traced
- ❌ Conflicts go undetected
- ❌ Compliance becomes impossible

**Trustworthy AI requires semantic accountability.**

---

## 🆚 Semantica vs Traditional RAG

| Traditional RAG | Semantica |
|-----------------|-----------|
| Black-box answers | Explainable reasoning |
| No provenance | Source-level traceability |
| Vector similarity only | Semantic + graph reasoning |
| No conflict handling | Explicit contradiction detection |
| Unsafe for high-stakes use | Designed for governed environments |

---

## 🧩 Semantica Architecture

### 1️⃣ Input Layer — Governed Ingestion
- PDFs, DOCX, HTML  
- JSON, CSV, databases  
- APIs, streams, archives  
- Multi-modal content  

All data enters through a **single ingestion pipeline** with metadata and source tracking.

---

### 2️⃣ Semantic Layer — Trust & Reasoning Engine

This layer enforces **governance by design**:

- Entity extraction & normalization  
- Relationship discovery & triplet generation  
- Automated ontology induction  
- **Entity deduplication** (Jaro-Winkler, disjoint properties)  
- **Conflict detection and resolution**  
- **Provenance tracking (source, time, confidence)**  
- **Reasoning trace generation**  
- Context engineering for grounded LLM outputs  

---

### 3️⃣ Output Layer — Auditable Knowledge Assets
- **Knowledge Graphs** (queryable, temporal, explainable)  
- **OWL Ontologies** (HermiT / Pellet validated)  
- **Vector Embeddings** (FastEmbed by default)  

Every AI response can be traced back to:
- Source documents
- Extracted entities & relations
- Ontology rules applied
- Reasoning steps used

---

## ⚙️ Core Capabilities (High-Stakes Ready)

- **Explainable GraphRAG** — Graph-based reasoning with inspectable paths  
- **Automated Ontology Generation** — Domain rules encoded explicitly  
- **Traceable Knowledge Graphs** — Full lineage and versioning  
- **Agent Memory with Guardrails** — Rule-validated agent actions  
- **Production-Grade QA** — Deduplication, conflict detection, validation  
- **LLM-Agnostic Design** — Works across providers with structured outputs  
- **Scalable Pipelines** — Parallel, modular, production-friendly  

---

## 🏥 Built for High-Stakes Domains

Semantica is designed for domains where **mistakes have real consequences**:

- **Healthcare & Life Sciences** — Clinical reasoning, audit trails  
- **Finance & Risk** — Explainable decisions, regulatory compliance  
- **Legal & Compliance** — Evidence-backed reasoning  
- **Cybersecurity & Intelligence** — Attribution and provenance  
- **Government & Defense** — Governed, auditable AI systems  

---

## 👥 Who Uses Semantica?

- **AI / ML Engineers** — Explainable GraphRAG & agents  
- **Data Engineers** — Governed semantic pipelines  
- **Knowledge Engineers** — Ontologies & KGs at scale  
- **Enterprise Teams** — Trustworthy AI infrastructure  
- **Risk & Compliance Teams** — Audit-ready systems  

---

## 📦 Installation

### Install from PyPI (Recommended)

```bash
pip install semantica
# or
pip install semantica[all]
```

## 📚 Resources

> **New to Semantica?** Check out the [**Cookbook**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook) for hands-on examples!

- [**Cookbook**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook) - Interactive notebooks
  - [Introduction](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction) - Getting started tutorials
  - [Advanced](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/advanced) - Advanced techniques
  - [Use Cases](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/use_cases) - Real-world applications

## ✨ Core Capabilities

| **Data Ingestion** | **Semantic Extract** | **Knowledge Graphs** | **Ontology** |
|:--------------------:|:----------------------:|:----------------------:|:--------------:|
| [Multiple Formats](#universal-data-ingestion) | [Entity & Relations](#semantic-intelligence-engine) | [Graph Analytics](#knowledge-graph-construction) | [Auto Generation](#ontology-generation--management) |
| **Context** | **GraphRAG** | **LLM Providers** | **Pipeline** |
| [Agent Memory, Context Graph, Context Retriever](#context-engineering--memory-systems) | [Hybrid RAG](#knowledge-graph-powered-rag-graphrag) | [100+ LLMs](#llm-providers-module) | [Parallel Workers](#pipeline-orchestration--parallel-processing) |
| **QA** | **Reasoning** | | |
| [Conflict Resolution](#production-ready-quality-assurance) | [Rule-based Inference](#reasoning--inference-engine) | | |

---

### Universal Data Ingestion

> **Multiple file formats** • PDF, DOCX, HTML, JSON, CSV, databases, feeds, archives

```python
from semantica.ingest import FileIngestor, WebIngestor, DBIngestor

file_ingestor = FileIngestor(recursive=True)
web_ingestor = WebIngestor(max_depth=3)
db_ingestor = DBIngestor(connection_string="postgresql://...")

sources = []
sources.extend(file_ingestor.ingest("documents/"))
sources.extend(web_ingestor.ingest("https://example.com"))
sources.extend(db_ingestor.ingest(query="SELECT * FROM articles"))

print(f" Ingested {len(sources)} sources")
```

[**Cookbook: Data Ingestion**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/02_Data_Ingestion.ipynb)

### Document Parsing & Processing

> **Multi-format parsing** • **Text normalization** • **Intelligent chunking**

```python
from semantica.parse import DocumentParser, DoclingParser
from semantica.normalize import TextNormalizer
from semantica.split import TextSplitter

# Standard parsing
parser = DocumentParser()
parsed = parser.parse("document.pdf", format="auto")

# Enhanced parsing with Docling (recommended for complex layouts/tables)
# Requires: pip install docling
docling_parser = DoclingParser(enable_ocr=True)
result = docling_parser.parse("complex_table.pdf")

print(f"Text (Markdown): {result['full_text'][:100]}...")
print(f"Extracted {len(result['tables'])} tables")
for i, table in enumerate(result['tables']):
    print(f"Table {i+1} headers: {table.get('headers', [])}")

# Normalize text
normalizer = TextNormalizer()
normalized = normalizer.normalize(parsed, clean_html=True, normalize_entities=True)

# Split into chunks
splitter = TextSplitter(method="token", chunk_size=1000, chunk_overlap=200)
chunks = splitter.split(normalized)
```

[**Cookbook: Document Parsing**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/03_Document_Parsing.ipynb) • [**Data Normalization**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/04_Data_Normalization.ipynb) • [**Chunking & Splitting**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/11_Chunking_and_Splitting.ipynb)

### Semantic Intelligence Engine

> **Entity & Relation Extraction** • NER, Relationships, Events, Triplets with LLM Enhancement

```python
from semantica.semantic_extract import NERExtractor, RelationExtractor

text = "Apple Inc., founded by Steve Jobs in 1976, acquired Beats Electronics for $3 billion."

# Extract entities
ner_extractor = NERExtractor(method="ml", model="en_core_web_sm")
entities = ner_extractor.extract(text)

# Extract relationships
relation_extractor = RelationExtractor(method="dependency", model="en_core_web_sm")
relationships = relation_extractor.extract(text, entities=entities)

print(f"Entities: {len(entities)}, Relationships: {len(relationships)}")
```

[**Cookbook: Entity Extraction**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/05_Entity_Extraction.ipynb) • [**Relation Extraction**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/06_Relation_Extraction.ipynb) • [**Advanced Extraction**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/advanced/01_Advanced_Extraction.ipynb)

### Knowledge Graph Construction

> **Production-Ready KGs** • Entity Resolution • Temporal Support • Graph Analytics

```python
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder

# Extract entities and relationships
ner_extractor = NERExtractor(method="ml", model="en_core_web_sm")
relation_extractor = RelationExtractor(method="dependency", model="en_core_web_sm")

entities = ner_extractor.extract(text)
relationships = relation_extractor.extract(text, entities=entities)

# Build knowledge graph
builder = GraphBuilder()
kg = builder.build({"entities": entities, "relationships": relationships})

print(f"Nodes: {len(kg.get('entities', []))}, Edges: {len(kg.get('relationships', []))}")
```

[**Cookbook: Building Knowledge Graphs**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/07_Building_Knowledge_Graphs.ipynb) • [**Graph Analytics**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/10_Graph_Analytics.ipynb)

### Embeddings & Vector Store

> **FastEmbed by default** • **Multiple backends** • **Semantic search**

```python
from semantica.embeddings import EmbeddingGenerator
from semantica.vector_store import VectorStore

# Generate embeddings
embedding_gen = EmbeddingGenerator(model_name="sentence-transformers/all-MiniLM-L6-v2", dimension=384)
embeddings = embedding_gen.generate_embeddings(chunks, data_type="text")

# Store in vector database
vector_store = VectorStore(backend="faiss", dimension=384)
vector_store.store_vectors(vectors=embeddings, metadata=[{"text": chunk} for chunk in chunks])

# Search
results = vector_store.search(query="supply chain", top_k=5)
```

[**Cookbook: Embedding Generation**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/12_Embedding_Generation.ipynb) • [**Vector Store**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/13_Vector_Store.ipynb)

### Graph Store & Triplet Store

> **Neo4j, FalkorDB, Amazon Neptune support** • **SPARQL queries** • **RDF triplets**

```python
from semantica.graph_store import GraphStore
from semantica.triplet_store import TripletStore

# Graph Store (Neo4j, FalkorDB)
graph_store = GraphStore(backend="neo4j", uri="bolt://localhost:7687", user="neo4j", password="password")
graph_store.add_nodes([{"id": "n1", "labels": ["Person"], "properties": {"name": "Alice"}}])

# Amazon Neptune Graph Store (OpenCypher via HTTP with IAM Auth)
neptune_store = GraphStore(
    backend="neptune",
    endpoint="your-cluster.us-east-1.neptune.amazonaws.com",
    port=8182,
    region="us-east-1",
    iam_auth=True,  # Uses AWS credential chain (boto3, env vars, or IAM role)
)

# Node Operations
neptune_store.add_nodes([
    {"labels": ["Person"], "properties": {"id": "alice", "name": "Alice", "age": 30}},
    {"labels": ["Person"], "properties": {"id": "bob", "name": "Bob", "age": 25}},
])

# Query Operations
result = neptune_store.execute_query("MATCH (p:Person) RETURN p.name, p.age")

# Triplet Store (Blazegraph, Jena, RDF4J)
triplet_store = TripletStore(backend="blazegraph", endpoint="http://localhost:9999/blazegraph")
triplet_store.add_triplet({"subject": "Alice", "predicate": "knows", "object": "Bob"})
results = triplet_store.execute_query("SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10")
```

[**Cookbook: Graph Store**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/09_Graph_Store.ipynb) • [**Triplet Store**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/20_Triplet_Store.ipynb)

### Ontology Generation & Management

> **6-Stage LLM Pipeline** • Automatic OWL Generation • HermiT/Pellet Validation

```python
from semantica.ontology import OntologyGenerator

generator = OntologyGenerator(llm_provider="openai", model="gpt-4")
ontology = generator.generate_from_documents(sources=["domain_docs/"])

print(f"Classes: {len(ontology.classes)}")
```

[**Cookbook: Ontology**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/14_Ontology.ipynb)

### Context Engineering & Memory Systems

> **Persistent Memory** • **Context Graph** • **Context Retriever** • **Hybrid Retrieval (Vector + Graph)** • **Production Graph Store (Neo4j)** • **Entity Linking** • **Multi-Hop Reasoning**

```python
from semantica.context import AgentContext, ContextGraph, ContextRetriever
from semantica.vector_store import VectorStore
from semantica.graph_store import GraphStore
from semantica.llms import Groq

# Initialize Context with Hybrid Retrieval (Graph + Vector)
context = AgentContext(
    vector_store=VectorStore(backend="faiss"),
    knowledge_graph=GraphStore(backend="neo4j"), # Optional: Use persistent graph
    hybrid_alpha=0.75  # 75% weight to Knowledge Graph, 25% to Vector
)

# Build Context Graph from entities and relationships
graph_stats = context.build_graph(
    entities=kg.get('entities', []),
    relationships=kg.get('relationships', []),
    link_entities=True
)

# Store memory with automatic entity linking
context.store(
    "User is building a RAG system with Semantica",
    metadata={"priority": "high", "topic": "rag"}
)

# Use Context Retriever for hybrid retrieval
retriever = context.retriever  # Access underlying ContextRetriever
results = retriever.retrieve(
    query="What is the user building?",
    max_results=10,
    use_graph_expansion=True
)

# Retrieve with context expansion
results = context.retrieve("What is the user building?", use_graph_expansion=True)

# Query with reasoning and LLM-generated responses
llm_provider = Groq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"))
reasoned_result = context.query_with_reasoning(
    query="What is the user building?",
    llm_provider=llm_provider,
    max_hops=2
)
```

**Core Components:**
- **ContextGraph**: Builds and manages context graphs from entities and relationships for enhanced retrieval
- **ContextRetriever**: Performs hybrid retrieval combining vector search, graph traversal, and memory for optimal context relevance
- **AgentContext**: High-level interface integrating Context Graph and Context Retriever for GraphRAG applications

**Core Notebooks:**
- [**Context Module Introduction**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/19_Context_Module.ipynb) - Basic memory and storage.
- [**Advanced Context Engineering**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/advanced/11_Advanced_Context_Engineering.ipynb) - Hybrid retrieval, graph builders, and custom memory policies.
- [**Fraud Detection**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/use_cases/finance/02_Fraud_Detection.ipynb) - Demonstrates Context Graph and Context Retriever for fraud detection with GraphRAG.

**Related Components:**
[**Vector Store**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/13_Vector_Store.ipynb) • [**Embedding Generation**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/12_Embedding_Generation.ipynb) • [**Advanced Vector Store**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/advanced/Advanced_Vector_Store_and_Search.ipynb)

### Knowledge Graph-Powered RAG (GraphRAG)

> **30% Accuracy Improvement** • Vector + Graph Hybrid Search • 91% Accuracy • **Multi-Hop Reasoning** • **LLM-Generated Responses**

```python
from semantica.context import AgentContext
from semantica.llms import Groq, OpenAI, LiteLLM
from semantica.vector_store import VectorStore
import os

# Initialize GraphRAG with hybrid retrieval
context = AgentContext(
    vector_store=VectorStore(backend="faiss"),
    knowledge_graph=kg
)

# Configure LLM provider (supports Groq, OpenAI, HuggingFace, LiteLLM)
llm_provider = Groq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY")
)

# Query with multi-hop reasoning and LLM-generated responses
result = context.query_with_reasoning(
    query="What IPs are associated with security alerts?",
    llm_provider=llm_provider,
    max_results=10,
    max_hops=2
)

print(f"Response: {result['response']}")
print(f"Reasoning Path: {result['reasoning_path']}")
print(f"Confidence: {result['confidence']:.3f}")
```

**Key Features:**
- **Multi-Hop Reasoning**: Traverses knowledge graph up to N hops to find related entities
- **LLM-Generated Responses**: Natural language answers grounded in graph context
- **Reasoning Trace**: Shows entity relationship paths used in reasoning
- **Multiple LLM Providers**: Supports Groq, OpenAI, HuggingFace, and LiteLLM (100+ LLMs)

[**Cookbook: GraphRAG**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb) • [**Real-Time Anomaly Detection**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/use_cases/cybersecurity/01_Real_Time_Anomaly_Detection.ipynb)

### LLM Providers Module

> **Unified LLM Interface** • **100+ LLM Support via LiteLLM** • **Clean Imports** • **Multiple Providers**

```python
from semantica.llms import Groq, OpenAI, HuggingFaceLLM, LiteLLM
import os

# Groq - Fast inference
groq = Groq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY")
)
response = groq.generate("What is AI?")

# OpenAI
openai = OpenAI(
    model="gpt-4",
    api_key=os.getenv("OPENAI_API_KEY")
)
response = openai.generate("What is AI?")

# HuggingFace - Local models
hf = HuggingFaceLLM(model_name="gpt2")
response = hf.generate("What is AI?")

# LiteLLM - Unified interface to 100+ LLMs
litellm = LiteLLM(
    model="openai/gpt-4o",  # or "anthropic/claude-sonnet-4-20250514", "groq/llama-3.1-8b-instant", etc.
    api_key=os.getenv("OPENAI_API_KEY")
)
response = litellm.generate("What is AI?")

# Structured output
structured = groq.generate_structured("Extract entities from: Apple Inc. was founded by Steve Jobs.")
```

**Supported Providers:**
- **Groq**: Fast inference with Llama models
- **OpenAI**: GPT-3.5, GPT-4, and other OpenAI models
- **HuggingFace**: Local LLM inference with Transformers
- **LiteLLM**: Unified interface to 100+ LLM providers (OpenAI, Anthropic, Azure, Bedrock, Vertex AI, and more)

### Reasoning & Inference Engine

> **Rule-based Inference** • **Forward/Backward Chaining** • **Rete Algorithm** • **Explanation Generation**

```python
from semantica.reasoning import Reasoner

# Initialize Reasoner
reasoner = Reasoner()

# Define rules and facts
rules = ["IF Parent(?a, ?b) AND Parent(?b, ?c) THEN Grandparent(?a, ?c)"]
facts = ["Parent(Alice, Bob)", "Parent(Bob, Charlie)"]

# Infer new facts (Forward Chaining)
inferred = reasoner.infer_facts(facts, rules)
print(f"Inferred: {inferred}") # ['Grandparent(Alice, Charlie)']

# Explain reasoning
from semantica.reasoning import ExplanationGenerator
explainer = ExplanationGenerator()
# ... generate explanation for inferred facts
```

[**Cookbook: Reasoning**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/advanced/08_Reasoning_and_Inference.ipynb) • [**Rete Engine**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/advanced/09_Rete_Engine.ipynb)

### Pipeline Orchestration & Parallel Processing

> **Orchestrator-Worker Pattern** • Parallel Execution • Scalable Processing

```python
from semantica.pipeline import PipelineBuilder, ExecutionEngine

pipeline = PipelineBuilder() \
    .add_step("ingest", "custom", func=ingest_data) \
    .add_step("extract", "custom", func=extract_entities) \
    .add_step("build", "custom", func=build_graph) \
    .build()

result = ExecutionEngine().execute_pipeline(pipeline, parallel=True)
```



### Production-Ready Quality Assurance

> **Enterprise-Grade QA** • Conflict Detection • Deduplication

```python
from semantica.deduplication import DuplicateDetector
from semantica.conflicts import ConflictDetector

entities = kg.get("entities", [])
conflicts = ConflictDetector().detect_conflicts(entities)
duplicates = DuplicateDetector(similarity_threshold=0.85).detect_duplicates(entities)

print(f"Conflicts: {len(conflicts)} | Duplicates: {len(duplicates)}")
```

[**Cookbook: Conflict Detection & Resolution**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/17_Conflict_Detection_and_Resolution.ipynb) • [**Deduplication**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/18_Deduplication.ipynb)

### Visualization & Export

> **Interactive graphs** • **Multi-format export** • **Graph analytics**

```python
from semantica.visualization import KGVisualizer
from semantica.export import GraphExporter

# Visualize knowledge graph
viz = KGVisualizer(layout="force")
fig = viz.visualize_network(kg, output="interactive")
fig.show()

# Export to multiple formats
exporter = GraphExporter()
exporter.export(kg, format="json", output_path="graph.json")
exporter.export(kg, format="graphml", output_path="graph.graphml")
```

[**Cookbook: Visualization**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/16_Visualization.ipynb) • [**Export**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/15_Export.ipynb)

### Seed Data Integration

> **Foundation data** • **Entity resolution** • **Domain knowledge**

```python
from semantica.seed import SeedDataManager

seed_manager = SeedDataManager()
seed_manager.seed_data.entities = [
    {"id": "s1", "text": "Supplier A", "type": "Supplier", "source": "foundation", "verified": True}
]

# Use seed data for entity resolution
resolved = seed_manager.resolve_entities(extracted_entities)
```

[**Cookbook: Seed Data**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/advanced/07_Seed_Data_Integration.ipynb)

## 🚀 Quick Start

> **For comprehensive examples, see the [**Cookbook**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook) with interactive notebooks!**

```python
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder
from semantica.context import AgentContext, ContextGraph
from semantica.vector_store import VectorStore

# Extract entities and relationships
ner_extractor = NERExtractor(method="ml", model="en_core_web_sm")
relation_extractor = RelationExtractor(method="dependency", model="en_core_web_sm")

text = "Apple Inc. was founded by Steve Jobs in 1976."
entities = ner_extractor.extract(text)
relationships = relation_extractor.extract(text, entities=entities)

# Build knowledge graph
builder = GraphBuilder()
kg = builder.build({"entities": entities, "relationships": relationships})

# Query using GraphRAG
vector_store = VectorStore(backend="faiss", dimension=384)
context_graph = ContextGraph()
context_graph.build_from_entities_and_relationships(
    entities=kg.get('entities', []),
    relationships=kg.get('relationships', [])
)
context = AgentContext(vector_store=vector_store, knowledge_graph=context_graph)

results = context.retrieve("Who founded Apple?", max_results=5)
print(f"Found {len(results)} results")
```

[**Cookbook: Your First Knowledge Graph**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/introduction/08_Your_First_Knowledge_Graph.ipynb)

## 🎯 Use Cases

**Enterprise Knowledge Engineering** — Unify data sources into knowledge graphs, breaking down silos.

**AI Agents & Autonomous Systems** — Build agents with persistent memory and semantic understanding.

**Multi-Format Document Processing** — Process multiple formats through a unified pipeline.

**Data Pipeline Processing** — Build scalable pipelines with parallel execution.

**Intelligence & Security** — Analyze networks, threat intelligence, forensic analysis.

**Finance & Trading** — Fraud detection, market intelligence, risk assessment.

**Biomedical** — Drug discovery, medical literature analysis.



## 🍳 Semantica Cookbook

> **Interactive Jupyter Notebooks** designed to take you from beginner to expert.

[**View Full Cookbook**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook)

### Featured Recipes

| **Recipe** | **Description** | **Link** |
|:-----------|:----------------|:---------|
| **GraphRAG Complete** | Build a production-ready **Graph Retrieval Augmented Generation** system. Features **Graph Validation**, **Hybrid Retrieval**, and **Logical Inference**. | [Open Notebook](cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb) |
| **RAG vs. GraphRAG** | Side-by-side comparison. Demonstrates the **Reasoning Gap** and how GraphRAG solves it with **Inference Engines**. | [Open Notebook](cookbook/use_cases/advanced_rag/02_RAG_vs_GraphRAG_Comparison.ipynb) |
| **First Knowledge Graph** | Go from raw text to a queryable knowledge graph in 20 minutes. | [Open Notebook](cookbook/introduction/08_Your_First_Knowledge_Graph.ipynb) |
| **Real-Time Anomalies** | Detect anomalies in streaming data using temporal knowledge graphs and pattern detection. | [Open Notebook](cookbook/use_cases/cybersecurity/01_Real_Time_Anomaly_Detection.ipynb) |

### Core Tutorials

- [**Welcome to Semantica**](cookbook/introduction/01_Welcome_to_Semantica.ipynb) - Framework Overview
- [**Data Ingestion**](cookbook/introduction/02_Data_Ingestion.ipynb) - Universal Ingestion
- [**Entity Extraction**](cookbook/introduction/05_Entity_Extraction.ipynb) - NER & Relationships
- [**Building Knowledge Graphs**](cookbook/introduction/07_Building_Knowledge_Graphs.ipynb) - Graph Construction

### Industry Use Cases (14 Cookbooks)

**Domain-Specific Cookbooks** showcasing real-world applications with real data sources, advanced chunking strategies, temporal KGs, GraphRAG, and comprehensive Semantica module integration:

#### Biomedical
- [**Drug Discovery Pipeline**](cookbook/use_cases/biomedical/01_Drug_Discovery_Pipeline.ipynb) - PubMed RSS, entity-aware chunking, GraphRAG, vector similarity search
- [**Genomic Variant Analysis**](cookbook/use_cases/biomedical/02_Genomic_Variant_Analysis.ipynb) - bioRxiv RSS, temporal KGs, deduplication, pathway analysis

#### Finance
- [**Financial Data Integration MCP**](cookbook/use_cases/finance/01_Financial_Data_Integration_MCP.ipynb) - Alpha Vantage API, MCP servers, seed data, real-time ingestion
- [**Fraud Detection**](cookbook/use_cases/finance/02_Fraud_Detection.ipynb) - Transaction streams, temporal KGs, pattern detection, conflict resolution, **Context Graph**, **Context Retriever**, GraphRAG with Groq LLM

#### Blockchain
- [**DeFi Protocol Intelligence**](cookbook/use_cases/blockchain/01_DeFi_Protocol_Intelligence.ipynb) - CoinDesk RSS, ontology-aware chunking, conflict detection, ontology generation
- [**Transaction Network Analysis**](cookbook/use_cases/blockchain/02_Transaction_Network_Analysis.ipynb) - Blockchain APIs, deduplication, network analytics

#### Cybersecurity
- [**Real-Time Anomaly Detection**](cookbook/use_cases/cybersecurity/01_Real_Time_Anomaly_Detection.ipynb) - CVE RSS, Kafka streams, temporal KGs, sentence chunking
- [**Threat Intelligence Hybrid RAG**](cookbook/use_cases/cybersecurity/02_Threat_Intelligence_Hybrid_RAG.ipynb) - Security RSS, entity-aware chunking, enhanced GraphRAG, deduplication

#### Intelligence & Law Enforcement
- [**Criminal Network Analysis**](cookbook/use_cases/intelligence/01_Criminal_Network_Analysis.ipynb) - OSINT RSS, deduplication, network centrality, graph analytics
- [**Intelligence Analysis Orchestrator Worker**](cookbook/use_cases/intelligence/02_Intelligence_Analysis_Orchestrator_Worker.ipynb) - Pipeline orchestrator, multi-source integration, conflict detection

#### Renewable Energy
- [**Energy Market Analysis**](cookbook/use_cases/renewable_energy/01_Energy_Market_Analysis.ipynb) - Energy RSS, EIA API, temporal KGs, TemporalPatternDetector, trend prediction

#### Supply Chain
- [**Supply Chain Data Integration**](cookbook/use_cases/supply_chain/01_Supply_Chain_Data_Integration.ipynb) - Logistics RSS, deduplication, relationship mapping


[**Explore Use Case Examples**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/use_cases) — See real-world implementations in finance, biomedical, cybersecurity, and more. **14 comprehensive domain-specific cookbooks** with real data sources, advanced chunking strategies, temporal KGs, GraphRAG, and full Semantica module integration.

## 🔬 Advanced Features

**Incremental Updates** — Real-time stream processing with Kafka, RabbitMQ, Kinesis for live updates.

**Multi-Language Support** — Process multiple languages with automatic detection.

**Custom Ontology Import** — Import and extend Schema.org and custom ontologies.

**Advanced Reasoning** — Forward/backward chaining, Rete-based pattern matching, and automated explanation generation.

**Graph Analytics** — Centrality, community detection, path finding, temporal analysis.

**Custom Pipelines** — Build custom pipelines with parallel execution.

**API Integration** — Integrate external APIs for entity enrichment.

[**See Advanced Examples**](https://github.com/Hawksight-AI/semantica/tree/main/cookbook/advanced) — Advanced extraction, graph analytics, reasoning, and more.

## 🗺️ Roadmap

### Q1 2026
- [x] Core framework (v1.0)
- [x] GraphRAG engine
- [x] 6-stage ontology pipeline
- [x] Advanced reasoning v2 (Rete, Forward/Backward Chaining)
- [ ] Quality assurance features and Quality Assurance module
- [ ] Enhanced multi-language support
- [ ] Evals
- [ ] Real-time streaming improvements

### Q2 2026
- [ ] Multi-modal processing

---

## 🤝 Community & Support

### Join Our Community

| **Channel** | **Purpose** |
|:-----------:|:-----------|
| [**Discord**](https://discord.gg/pMHguUzG) | Real-time help, showcases |
| [**GitHub Discussions**](https://github.com/Hawksight-AI/semantica/discussions) | Q&A, feature requests |

### Learning Resources


### Enterprise Support

Enterprise support, professional services, and commercial licensing will be available in the future. For now, we offer community support through Discord and GitHub Discussions.

**Current Support:**
- **Community Support** - Free support via [Discord](https://discord.gg/pMHguUzG) and [GitHub Discussions](https://github.com/Hawksight-AI/semantica/discussions)
- **Bug Reports** - [GitHub Issues](https://github.com/Hawksight-AI/semantica/issues)

**Future Enterprise Offerings:**
- Professional support with SLA
- Enterprise licensing
- Custom development services
- Priority feature requests
- Dedicated support channels

Stay tuned for updates!

## 🤝 Contributing

### How to Contribute

```bash
# Fork and clone
git clone https://github.com/your-username/semantica.git
cd semantica

# Create branch
git checkout -b feature/your-feature

# Install dev dependencies
pip install -e ".[dev,test]"

# Make changes and test
pytest tests/
black semantica/
flake8 semantica/

# Commit and push
git commit -m "Add feature"
git push origin feature/your-feature
```

### Contribution Types

1. **Code** - New features, bug fixes
2. **Documentation** - Improvements, tutorials
3. **Bug Reports** - [Create issue](https://github.com/Hawksight-AI/semantica/issues/new)
4. **Feature Requests** - [Request feature](https://github.com/Hawksight-AI/semantica/issues/new)


###  Contributors

<a href="https://github.com/Hawksight-AI/semantica/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Hawksight-AI/semantica" alt="Contributors" />
</a>

## 📜 License

Semantica is licensed under the **MIT License** - see the [LICENSE](https://github.com/Hawksight-AI/semantica/blob/main/LICENSE) file for details.

<div align="center">

**Built by the Semantica Community**

[GitHub](https://github.com/Hawksight-AI/semantica) • [Discord](https://discord.gg/pMHguUzG)

</div>
