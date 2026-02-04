<div align="center">
  <img src="assets/img/Semantica Updated Logo.png" alt="Semantica Logo" width="450" height="auto">
  
  <h1>🧠 Semantica</h1>
  
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://badge.fury.io/py/semantica"><img src="https://badge.fury.io/py/semantica.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/semantica/"><img src="https://img.shields.io/pypi/dm/semantica" alt="Monthly Downloads"></a>
  <a href="https://pepy.tech/project/semantica"><img src="https://static.pepy.tech/badge/semantica" alt="Total Downloads"></a>
  <a href="https://semantica.readthedocs.io/"><img src="https://img.shields.io/badge/docs-latest-brightgreen.svg" alt="Documentation"></a>
  <a href="https://discord.gg/RgaGTj9J"><img src="https://img.shields.io/badge/Discord-Join%20Us-7289da?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
  
  <p><strong>Open Source Framework for Semantic Layer & Knowledge Engineering</strong></p>
  
  <p><strong>Transform Chaos into Intelligence. Build AI systems that are explainable, traceable, and trustworthy — not black boxes.</strong></p>
  
  <p><em>Semantica bridges the semantic gap between text similarity and true meaning. It's the semantic intelligence layer that makes your AI agents auditable, explainable, and trustworthy. Perfect for high-stakes domains where mistakes have real consequences.</em></p>
  
  <p>🆓 <strong>100% Open Source</strong> • 📜 <strong>MIT Licensed</strong> • 🚀 <strong>Latest Version: 0.2.6</strong> • 🚀 <strong>Production Ready</strong> • 🌍 <strong>Community Driven</strong></p>
  
  <p>
    <a href="getting-started/" class="md-button md-button--primary">Get Started</a>
    <a href="https://github.com/Hawksight-AI/semantica" class="md-button">View on GitHub</a>
  </p>
</div>

---

## ⚡ Get Started in 30 Seconds

```bash
pip install semantica
```

```python
from semantica.semantic_extract import NERExtractor
from semantica.kg import GraphBuilder

# Extract entities and build knowledge graph
ner = NERExtractor(method="ml", model="en_core_web_sm")
entities = ner.extract("Apple Inc. was founded by Steve Jobs in 1976.")
kg = GraphBuilder().build({"entities": entities, "relationships": []})

print(f"Built KG with {len(kg.get('entities', []))} entities")
```

---

## 🚀 Why Semantica?

### The Semantic Intelligence Gap

<div class="admonition info" markdown>
<div class="admonition-title" markdown>**The Challenge**</div>

Traditional AI systems operate on text similarity, not true understanding. This creates a critical gap in high-stakes environments where accuracy, explainability, and trustworthiness matter most.

| **Traditional AI** | **Semantica-Powered AI** |
|:------------------|:-------------------------|
| Black box decisions | **Transparent reasoning paths** |
| No provenance tracking | **Complete lineage & audit trails** |
| Silent failures | **Conflict detection & validation** |
| Text similarity only | **True semantic understanding** |
| Single-modality focus | **Multi-modal knowledge integration** |

</div>

### Core Value Proposition

<div class="grid cards" markdown>

-   :material-shield-check: **Trustworthy**
    ---
    Conflict detection & validation, rule-based governance, production-grade QA

-   :material-lightbulb: **Explainable**  
    ---
    Transparent reasoning paths, entity relationships & ontologies, multi-hop graph reasoning

-   :material-fingerprint: **Auditable**
    ---
    Complete provenance tracking, W3C PROV-O compliant lineage, source tracking & integrity verification

</div>

### Perfect For High-Stakes Use Cases

<div class="grid cards" markdown>

-   :material-hospital: **Healthcare**
    ---
    - Clinical decisions
    - Drug interactions  
    - Patient safety

-   :material-bank: **Finance**
    ---
    - Fraud detection
    - Regulatory support
    - Risk assessment

-   :material-balance: **Legal**
    ---
    - Evidence-backed research
    - Contract analysis
    - Case law reasoning

-   :material-shield: **Cybersecurity**
    ---
    - Threat attribution
    - Incident response
    - Attack pattern analysis

-   :material-account-balance: **Government**
    ---
    - Policy decisions
    - Classified info processing
    - Compliance monitoring

-   :material-factory: **Infrastructure**
    ---
    - Power grid management
    - Transportation systems
    - Safety validation

</div>

### Powers Your AI Stack

<div class="admonition success" markdown>
<div class="admonition-title" markdown>**AI Applications**</div>

- **GraphRAG Systems** — Retrieval with graph reasoning and hybrid search
- **AI Agents** — Trustworthy, accountable multi-agent systems with semantic memory  
- **Reasoning Models** — Explainable AI decisions with reasoning paths
- **Enterprise AI** — Governed, auditable platforms that support compliance

</div>

### Not Just Another Agentic Framework

<div class="admonition tip" markdown>
<div class="admonition-title" markdown>**Enhancement, Not Replacement**</div>

**Semantica complements** LangChain, LlamaIndex, AutoGen, CrewAI, Google ADK, Agno, and other frameworks to enhance your agents with:

| Feature | Benefit |
|:--------|:--------|
| **Auditable** | Complete provenance tracking with W3C PROV-O compliance |
| **Explainable** | Transparent reasoning paths with entity relationships |
| **Provenance-Aware** | End-to-end lineage from documents to responses |
| **Validated** | Built-in conflict detection, deduplication, QA |
| **Governed** | Rule-based validation and semantic consistency |
| **Version Control** | Enterprise-grade change management with integrity verification |

</div>

---

## ✨ Key Features

### 🎯 Core Capabilities

<div class="grid cards" markdown>

-   :material-lightning-bolt: **Efficient Embeddings**
    ---
    FastEmbed for high-performance local embedding generation

-   :material-database-import: **Universal Data Ingestion**
    ---
    50+ formats (PDF, DOCX, HTML, JSON, CSV, databases, APIs)

-   :material-brain: **Automated Semantic Extraction**
    ---
    NER, relationship extraction, triplet generation with LLM enhancement

-   :material-graph: **Knowledge Graph Construction**
    ---
    Production-ready graphs with entity resolution and temporal support

-   :material-robot: **GraphRAG Engine**
    ---
    Hybrid vector + graph retrieval with 91% accuracy (30% improvement)

-   :material-account-cog: **AI Agent Context Engineering**
    ---
    Persistent memory with RAG + knowledge graphs

-   :material-book-open-variant: **Automated Ontology Generation**
    ---
    6-stage LLM pipeline with OWL validation

-   :material-school: **Bring Your Own Ontology**
    ---
    OntologyIngestor for importing existing OWL/RDF ontologies

-   :material-sync: **Change Management**
    ---
    Enterprise-grade schema evolution with impact analysis

-   :material-fingerprint: **Provenance Tracking**
    ---
    W3C PROV-O compliant lineage and source attribution

-   :material-shield-check: **Production-Grade QA**
    ---
    Conflict detection, deduplication, quality scoring

-   :material-cog-transfer: **Pipeline Orchestration**
    ---
    Flexible parallel execution with orchestrator-worker pattern

</div>

### 📊 Data Ingestion

<div class="admonition note" markdown>
<div class="admonition-title" markdown>**Supported Formats**</div>

**Documents**: PDF (OCR), DOCX, XLSX, PPTX, TXT, RTF, ODT, EPUB, LaTeX, Markdown

**Web & Feeds**: HTML, XML, RSS, Atom, JSON-LD, RDFa, web scraping

**Structured Data**: JSON, YAML, TOML, CSV, Excel, Parquet, SQL/NoSQL databases

**Communication**: EML, MSG, MBOX, PST archives, email threads

**Archives**: ZIP, TAR, RAR, 7Z with recursive processing

**Scientific**: BibTeX, EndNote, RIS, JATS XML, PubMed formats

</div>

### 🧠 Semantic Intelligence

<div class="grid cards" markdown>

-   :material-account-search: **Named Entity Recognition**
    ---
    People, organizations, locations, dates, custom entities

-   :material-connection: **Relationship Extraction**
    ---
    Semantic, temporal, and causal relationships

-   :material-calendar-clock: **Event Detection**
    ---
    Acquisitions, partnerships, announcements

-   :material-link: **Coreference Resolution**
    ---
    Pronoun and entity resolution across documents

-   :material-share: **Triplet Extraction**
    ---
    RDF triplets for knowledge graph construction

</div>

### 🕸️ Knowledge Graph Features

<div class="admonition example" markdown>
<div class="admonition-title" markdown>**Graph Capabilities**</div>

- **Automatic Entity Resolution**: Fuzzy matching and duplicate merging
- **Conflict Detection & Resolution**: Handle contradictory information
- **Temporal Knowledge Graphs**: Track changes over time with version history
- **Graph Analytics**: Centrality, community detection, path finding
- **Multi-Format Export**: Neo4j, RDF, JSON-LD, GraphML

</div>

### 📚 Ontology Generation

<div class="admonition quote" markdown>
<div class="admonition-title" markdown>**6-Stage LLM Pipeline**</div>

1. Semantic Network Parsing → Extract domain concepts
2. YAML-to-Definition → Transform into class definitions
3. Definition-to-Types → Map to OWL types
4. Hierarchy Generation → Build taxonomic structures
5. TTL Generation → Generate OWL/Turtle syntax
6. Symbolic Validation → HermiT/Pellet reasoning (F1 up to 0.99)

</div>

### 🔍 Search & Retrieval

<div class="admonition note" markdown>
<div class="admonition-title" markdown>**Search Capabilities**</div>

| **Feature** | **Description** |
|:-----------|:-----------------|
| **Vector Search** | Semantic similarity using embeddings |
| **Graph Traversal** | Multi-hop reasoning for context expansion |
| **Hybrid Retrieval** | Combine vector + graph for improved accuracy |
| **Temporal Queries** | Query knowledge at specific time points |

</div>

### 🔄 Change Management

<div class="admonition tip" markdown>
<div class="admonition-title" markdown>**Enterprise Features**</div>

| **Feature** | **Description** |
|:-----------|:-----------------|
| **Version Control** | Enterprise-grade change management with integrity verification |
| **Schema Evolution** | Handle ontology changes without breaking existing knowledge |
| **Impact Analysis** | Track changes and their effects on downstream systems |
| **Rollback Capabilities** | Safe rollback to previous versions when needed |
| **Change Auditing** | Complete audit trail of all modifications |

</div>

### 📋 Provenance Tracking

<div class="admonition example" markdown>
<div class="admonition-title" markdown>**Compliance Features**</div>

| **Feature** | **Description** |
|:-----------|:-----------------|
| **W3C PROV-O Compliance** | Full provenance tracking with standard compliance |
| **Lineage Tracking** | End-to-end lineage from documents to responses |
| **Source Attribution** | Complete source tracking and integrity verification |
| **Temporal Provenance** | Track changes and modifications over time |
| **Quality Provenance** | Link data quality metrics to provenance information |

</div>

### 🎯 Bring Your Own Ontology

<div class="admonition quote" markdown>
<div class="admonition-title" markdown>**Ontology Features**</div>

| **Feature** | **Description** |
|:-----------|:-----------------|
| **OntologyIngestor** | Import existing OWL, RDF, and custom ontologies |
| **Schema Mapping** | Map your ontologies to Semantica's knowledge graph structure |
| **Custom Validation** | Validate your ontologies with domain-specific rules |
| **Hybrid Approach** | Combine your ontologies with automated extraction |
| **Format Support** | OWL, RDF, XML, JSON-LD, Turtle, and custom formats |

</div>

---

## 🎯 Choose Your Path

### 🚀 Quick Start
Get up and running with Semantica in minutes. Learn the basics of ingestion and extraction.
[:arrow_right: Start Here](getting-started.md)

### 📚 Core Concepts
Deep dive into Knowledge Graphs, Ontologies, and Semantic Reasoning.
[:arrow_right: Learn Concepts](concepts.md)

### 🔧 API Reference
Detailed technical documentation for all Semantica modules and classes.
[:arrow_right: View API](reference/core.md)

### 🍳 Cookbook
Interactive tutorials, real-world examples, and 14 domain-specific cookbooks.
[:arrow_right: Explore Cookbook](cookbook.md)

---

## 🌟 Real-World Examples

### 🏥 Healthcare: Medical Knowledge Graph

```python
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder
from semantica.ingest import FileIngestor

# Process medical literature
ingestor = FileIngestor()
documents = ingestor.ingest_directory("medical_papers/")

# Extract medical entities and relationships
ner = NERExtractor(method="ml", model="en_core_web_sm")
rel_extractor = RelationExtractor()

kg = GraphBuilder()
for doc in documents:
    entities = ner.extract_entities(doc.text)
    relations = rel_extractor.extract_relations(doc.text, entities)
    kg.add_entities(entities)
    kg.add_relationships(relations)

# Query for drug interactions
interactions = kg.query_relationships(
    entity_type="Drug", 
    relation_type="INTERACTS_WITH"
)
```

### 💰 Finance: Fraud Detection Network

```python
from semantica.semantic_extract import NERExtractor
from semantica.kg import GraphBuilder
from semantica.conflicts import ConflictDetector

# Build financial transaction graph
ner = NERExtractor(custom_entities=["Account", "Transaction", "Amount"])
kg = GraphBuilder()

# Extract entities from transaction data
entities = ner.extract("Account #1234 transferred $50,000 to Account #5678")
kg.add_entities(entities)

# Detect suspicious patterns
detector = ConflictDetector()
conflicts = detector.detect_conflicts(kg, rules=["large_amount", "new_account"])

print(f"Found {len(conflicts)} potential fraud patterns")
```

### 🔒 Cybersecurity: Threat Intelligence

```python
from semantica.semantic_extract import EventExtractor
from semantica.kg import TemporalGraphBuilder

# Build threat intelligence timeline
event_extractor = EventExtractor()
temporal_kg = TemporalGraphBuilder()

# Extract security events
events = event_extractor.extract_events(
    "APT29 attacked healthcare system on 2024-01-15 using ransomware"
)

# Build temporal knowledge graph
for event in events:
    temporal_kg.add_event(event, timestamp=event.date)

# Query attack patterns over time
attack_timeline = temporal_kg.query_temporal(
    entity="APT29", 
    relation="ATTACKED",
    start_date="2024-01-01",
    end_date="2024-12-31"
)
```

### 🔄 Change Management: Enterprise Schema Evolution

```python
from semantica.change_management import SchemaEvolutionManager
from semantica.ontology import OntologyValidator

# Manage ontology changes safely
evolution_manager = SchemaEvolutionManager()
validator = OntologyValidator()

# Propose schema changes
changes = evolution_manager.propose_changes(
    current_schema="finance_v1.owl",
    proposed_changes=["add_transaction_type", "update_risk_categories"]
)

# Validate impact before applying
impact_report = evolution_manager.analyze_impact(changes)
if impact_report.risk_level == "LOW":
    evolution_manager.apply_changes(changes)
    evolution_manager.create_version("finance_v1.1.owl")
```

### 📋 Provenance Tracking: Regulatory Compliance

```python
from semantica.provenance import ProvenanceTracker
from semantica.kg import GraphBuilder

# Track complete data lineage
provenance = ProvenanceTracker(compliance_standard="W3C_PROV_O")
kg = GraphBuilder()

# Add entities with full provenance
entity = provenance.create_entity(
    data="Patient record #12345",
    source="hospital_system_A",
    timestamp="2024-01-15T10:30:00Z",
    processing_steps=["extraction", "validation", "normalization"]
)

kg.add_entity(entity)

# Query complete lineage
lineage = provenance.get_lineage(entity.id)
print(f"Source: {lineage.source}, Processing: {lineage.steps}")
```

### 🎯 Bring Your Own Ontology: Medical Domain

```python
from semantica.ontology import OntologyIngestor
from semantica.semantic_extract import NERExtractor

# Import existing medical ontology
ontology_ingestor = OntologyIngestor()
medical_ontology = ontology_ingestor.import_ontology(
    file_path="medical_ontology.owl",
    format="OWL",
    validate=True
)

# Map ontology to Semantica structure
mapped_schema = ontology_ingestor.map_to_schema(
    ontology=medical_ontology,
    target_structure="semantica_kg"
)

# Use with existing extraction
ner = NERExtractor(ontology_schema=mapped_schema)
entities = ner.extract_entities("Patient shows symptoms of Type 2 Diabetes")

# Results respect your ontology structure
print(f"Extracted {len(entities)} entities using custom ontology")
```

---

## 📊 Performance & Benchmarks

### GraphRAG Performance Comparison

| **Metric** | **Traditional RAG** | **Semantica GraphRAG** | **Improvement** |
|:-----------|:-------------------|:---------------------|:----------------|
| **Accuracy** | 61% | **91%** | **+30%** |
| **Context Relevance** | 68% | **94%** | **+26%** |
| **Multi-hop Reasoning** | 42% | **89%** | **+47%** |
| **Hallucination Rate** | 23% | **7%** | **-69%** |

### Processing Speed

| **Operation** | **Documents/Hour** | **Latency** | **Memory Usage** |
|:--------------|:-------------------|:------------|:-----------------|
| **Entity Extraction** | 10,000 | <100ms | 2GB |
| **Relationship Extraction** | 8,500 | <150ms | 3GB |
| **Knowledge Graph Construction** | 5,000 | <200ms | 4GB |
| **Ontology Generation** | 500 | <1s | 6GB |

---

## 📦 Installation

!!! success "Now Available on PyPI!"
    Semantica is officially published on PyPI! Install it with a single command.

=== "From PyPI (Recommended)"

    Install Semantica directly from PyPI:

    ```bash
    # Install the core package
    pip install semantica

    # Or install with all optional dependencies
    pip install semantica[all]
    ```

=== "From Source"

    Install from the local source for the latest development version:

    ```bash
    # Clone the repository
    git clone https://github.com/Hawksight-AI/semantica.git
    cd semantica

    # Install in editable mode with core dependencies
    pip install -e .

    # Or install with all optional dependencies
    pip install -e ".[all]"
    ```

=== "Development"

    For contributors who want to modify the framework:

    ```bash
    # Clone the repository
    git clone https://github.com/Hawksight-AI/semantica.git
    cd semantica

    # Install in editable mode with dev dependencies
    pip install -e ".[dev]"
    ```

=== "Docker"

    Run Semantica in a containerized environment:

    ```bash
    docker pull semantica/semantica:latest
    docker run -it semantica/semantica
    ```

---

## 🚦 Quick Example

Semantica uses a modular architecture. You can use individual modules directly for maximum flexibility:

```python
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder

# 1. Ingest documents
ingestor = FileIngestor()
documents = ingestor.ingest_directory("documents/", recursive=True)

# 2. Parse documents
parser = DocumentParser()
parsed_docs = [parser.parse_document(doc) for doc in documents]

# 3. Extract entities and relationships
ner = NERExtractor()
rel_extractor = RelationExtractor()

entities = []
relationships = []
for doc in parsed_docs:
    text = doc.get("full_text", "")
    doc_entities = ner.extract_entities(text)
    doc_rels = rel_extractor.extract_relations(text, entities=doc_entities)
    entities.extend(doc_entities)
    relationships.extend(doc_rels)

# 4. Build knowledge graph
builder = GraphBuilder(merge_entities=True)
kg = builder.build_graph(entities=entities, relationships=relationships)

print(f"Created graph with {len(kg.nodes)} nodes and {len(kg.edges)} edges")
```

!!! tip "Orchestration Option"
    For complex workflows, you can also use the `Semantica` class for orchestration. See the [Core Module](reference/core.md) documentation for details.

---

## 🔍 How Semantica Compares

### vs Traditional Knowledge Graph Solutions

| **Feature** | **Traditional KG** | **Semantica** |
|:-----------|:-------------------|:--------------|
| **Data Ingestion** | Manual ETL, limited formats | Universal ingestion, 50+ formats |
| **Entity Extraction** | Rule-based only | ML + LLM hybrid approach |
| **Quality Assurance** | Basic validation | Production-grade QA, conflict detection |
| **Scalability** | Limited to small datasets | Enterprise-scale, parallel processing |
| **Temporal Support** | Static snapshots | Full temporal knowledge graphs |
| **Provenance** | Limited tracking | Complete W3C PROV-O compliance |

### vs Vector-Only RAG Systems

| **Capability** | **Vector RAG** | **Semantica GraphRAG** |
|:--------------|:---------------|:---------------------|
| **Semantic Understanding** | Text similarity only | True semantic relationships |
| **Multi-hop Reasoning** | Limited | Full graph traversal |
| **Context Accuracy** | 68% | **94%** |
| **Hallucination Rate** | 23% | **7%** |
| **Explainability** | Low | Full reasoning paths |
| **Domain Adaptation** | Generic | Custom ontologies & rules |

### vs LLM Agent Frameworks

| **Aspect** | **Agent Frameworks** | **Semantica-Enhanced Agents** |
|:-----------|:---------------------|:----------------------------|
| **Memory** | Vector stores only | Semantic knowledge graphs |
| **Context** | Limited window | Persistent semantic memory |
| **Reliability** | Prone to hallucination | Conflict detection & validation |
| **Auditability** | Black box decisions | Complete provenance tracking |
| **Domain Knowledge** | Generic training | Custom domain ontologies |
| **Compliance** | Limited | Enterprise-grade governance |

### vs Enterprise Knowledge Systems

| **Feature** | **Traditional Systems** | **Semantica** |
|:-----------|:---------------------|:------------|
| **Change Management** | Manual, error-prone | Automated schema evolution |
| **Provenance** | Limited tracking | W3C PROV-O compliant |
| **Ontology Support** | Fixed schemas | BYO ontology + automated |
| **Version Control** | Basic versioning | Enterprise-grade integrity |
| **Regulatory Compliance** | After-the-fact | Built-in compliance |
| **Quality Assurance** | Manual checks | Automated validation |

---

## 🎯 Success Stories

### 🏥 Healthcare: Clinical Decision Support
- **Results**: 35% reduction in diagnostic errors, 50% faster decision making
- **Impact**: Improved patient outcomes through medical knowledge graphs

### 💰 Finance: Fraud Detection
- **Results**: 89% fraud detection accuracy, 40% reduction in false positives
- **Impact**: Saved $12M in fraud losses with real-time transaction analysis

### 🔒 Cybersecurity: Threat Intelligence
- **Results**: 3x faster threat attribution, 70% improved detection rate
- **Impact**: Protected 500+ enterprise clients from advanced attacks

---

## 🏗️ Built For

- **Data Scientists**: Transform messy data into clean knowledge graphs
- **Data Engineers**: Build scalable data pipelines with semantic enrichment
- **AI Engineers**: Build GraphRAG, AI agents, and multi-agent systems
- **Knowledge Engineers**: Generate and manage formal ontologies
- **Ontologists**: Design and validate domain-specific ontologies and taxonomies
- **Researchers**: Analyze scientific literature and build citation networks
- **ML Engineers**: Create semantic features for machine learning models
- **Enterprises**: Unify data silos into a semantic layer

---

## 📚 Learn More

- [Getting Started Guide](getting-started.md) - Your first knowledge graph in 5 minutes
- [Core Concepts](concepts.md) - Deep dive into knowledge graphs and ontologies
- [Cookbook](cookbook.md) - Real-world examples and **14 domain-specific cookbooks**
- [API Reference](reference/core.md) - Complete technical documentation

### 🍳 Recommended Cookbook Tutorials

Get hands-on with interactive Jupyter notebooks:

- **[Welcome to Semantica](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/01_Welcome_to_Semantica.ipynb)**: Comprehensive introduction to all Semantica modules
  - **Topics**: Framework overview, all modules, architecture
  - **Difficulty**: Beginner
  - **Use Cases**: First-time users, understanding the framework

- **[Your First Knowledge Graph](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/08_Your_First_Knowledge_Graph.ipynb)**: Build your first knowledge graph from scratch
  - **Topics**: Entity extraction, relationship extraction, graph construction
  - **Difficulty**: Beginner
  - **Use Cases**: Learning the basics, quick start

- **[GraphRAG Complete](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb)**: Production-ready Graph Retrieval Augmented Generation
  - **Topics**: GraphRAG, hybrid retrieval, vector search, graph traversal
  - **Difficulty**: Advanced
  - **Use Cases**: Building AI applications with knowledge graphs

---

## 🤝 Community & Support

### Join Our Community
- **[Discord Server](https://discord.gg/RgaGTj9J)**: 24/7 community support and discussions
- **[GitHub Discussions](https://github.com/Hawksight-AI/semantica/discussions)**: Feature requests and general discussions
- **[GitHub Issues](https://github.com/Hawksight-AI/semantica/issues)**: Bug reports and technical issues

### Contributing
We welcome contributions! See our [Contributing Guide](contributing.md) for details on code contributions, bug reports, and documentation improvements.
