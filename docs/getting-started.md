# Getting Started

## Welcome to Semantica

<div class="admonition success" markdown>
<div class="admonition-title" markdown>**Semantic Intelligence Layer**</div>

**Semantica** bridges the semantic gap between text similarity and true meaning. It's the semantic intelligence layer that makes your AI agents auditable, explainable, and trustworthy — perfect for high-stakes domains where mistakes have real consequences.

</div>

### 🎯 What You'll Learn

<div class="grid cards" markdown>

-   :material-school: **Trustworthy AI**
    ---
    How Semantica makes AI systems trustworthy and explainable

-   :material-rocket-launch: **Quick Setup**
    ---
    Installation and quick setup in 30 seconds

-   :material-brain: **Core Concepts**
    ---
    Semantic layers, knowledge graphs, and provenance

-   :material-graph: **First Knowledge Graph**
    ---
    Building your first knowledge graph

-   :material-shield-check: **Enterprise Features**
    ---
    Production-grade features for enterprise use

</div>

---

## 🚀 Why Semantica?

<div class="admonition tip" markdown>
<div class="admonition-title" markdown>**Transform Chaos into Intelligence**</div>

Semantica transforms chaotic data into intelligence with comprehensive semantic understanding and enterprise-grade reliability.

</div>

### Core Value Proposition

<div class="grid cards" markdown>

-   :material-shield-check: **Trustworthy AI**
    ---
    Conflict detection, validation, and quality assurance

-   :material-lightbulb: **Explainable Systems**
    ---
    Transparent reasoning paths and entity relationships

-   :material-fingerprint: **Auditable Processes**
    ---
    Complete provenance tracking with W3C PROV-O compliance

-   :material-factory: **Production Ready**
    ---
    Battle-tested for high-stakes domains

</div>

### Perfect For High-Stakes Domains

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
    - Classified info
    - Compliance monitoring

-   :material-factory: **Infrastructure**
    ---
    - Power grid management
    - Transportation systems
    - Safety validation

</div>

---

## 💡 Key Applications

<div class="admonition example" markdown>
<div class="admonition-title" markdown>**AI Applications**</div>

Semantica powers next-generation AI systems with semantic understanding and enterprise-grade reliability.

</div>

<div class="grid cards" markdown>

-   :material-robot: **GraphRAG Systems**
    ---
    Retrieval with graph reasoning and hybrid search

-   :material-account-cog: **AI Agents**
    ---
    Trustworthy, accountable multi-agent systems

-   :material-domain: **Enterprise AI**
    ---
    Governed, auditable platforms for compliance

-   :material-microscope: **Research**
    ---
    Scientific literature analysis and knowledge management

-   :material-hospital: **Healthcare**
    ---
    Medical decision support and drug interaction analysis

-   :material-bank: **Finance**
    ---
    Fraud detection and regulatory compliance

</div>

---

## 📦 Installation & Setup

<div class="admonition success" markdown>
<div class="admonition-title" markdown>**Quick Installation**</div>

Get started with Semantica in just 30 seconds with our streamlined installation process.

</div>

### Prerequisites

<div class="grid cards" markdown>

-   :material-python: **Python 3.8+**
    ---
    Required for all Semantica functionality

-   :material-package: **pip Package Manager**
    ---
    For installing Python packages

-   :material-layers: **Virtual Environment**
    ---
    Optional but recommended for isolation

</div>

### Installation Methods

<div class="admonition tip" markdown>
<div class="admonition-title" markdown>**Choose Your Installation Method**</div>

Select the installation method that best fits your needs - from quick start to full development setup.

</div>

<div class="grid cards" markdown>

-   :material-rocket: **PyPI (Recommended)**
    ---
    Quick and easy installation from PyPI package repository

-   :material-source-merge: **Source Installation**
    ---
    Install from source for latest development features

-   :material-tools: **Development Setup**
    ---
    Full development environment with all dependencies

-   :material-docker: **Docker**
    ---
    Containerized environment for consistent deployment

</div>

### Verify Installation

```python
import semantica
print(semantica.__version__)
```

---

## ⚡ Quick Start: 30 Seconds to Your First Knowledge Graph

<div class="admonition example" markdown>
<div class="admonition-title" markdown>**Your First Knowledge Graph**</div>

Get started immediately with this simple example that demonstrates Semantica's core capabilities.

</div>

### Step 1: Install Semantica

```bash
pip install semantica
```

### Step 2: Extract Entities and Build Graph

```python
from semantica.semantic_extract import NERExtractor
from semantica.kg import GraphBuilder

# Extract entities and build knowledge graph
ner = NERExtractor(method="ml", model="en_core_web_sm")
entities = ner.extract("Apple Inc. was founded by Steve Jobs in 1976.")
kg = GraphBuilder().build({"entities": entities, "relationships": []})

print(f"Built KG with {len(kg.get('entities', []))} entities")
```

### Step 3: Explore Your Knowledge Graph

```python
# Query your knowledge graph
all_entities = kg.get('entities', [])
for entity in all_entities:
    print(f"Entity: {entity.get('text', 'Unknown')} - Type: {entity.get('type', 'Unknown')}")

# Export to different formats if needed
kg.export_to_json("my_first_kg.json")
kg.export_to_rdf("my_first_kg.rdf")
```

<div class="admonition tip" markdown>
<div class="admonition-title" markdown>**Success!**</div>

**That's it!** You've just created your first knowledge graph with Semantica. The extracted entities are now ready for semantic analysis, graph traversal, and integration with AI applications.

</div>

---

## 🏗️ Understanding Semantica's Architecture

<div class="admonition note" markdown>
<div class="admonition-title" markdown>**Modular Design**</div>

Semantica uses a **modular architecture** where each module handles a specific aspect of semantic processing, giving you flexibility and control over your pipeline.

</div>

### Primary Approach: Individual Modules

<div class="grid cards" markdown>

-   :material-database-import: **Ingestion Layer**
    ---
    - FileIngestor, APIIngestor, DatabaseIngestor
    - Format detection and parsing
    - Batch and streaming support

-   :material-cog: **Processing Layer**
    ---
    - DocumentParser, TextProcessor
    - Normalization and preprocessing
    - Multi-modal content handling

-   :material-brain: **Semantic Layer**
    ---
    - NERExtractor, RelationExtractor, EventExtractor
    - LLM-enhanced extraction
    - Custom entity and relation support

-   :material-graph: **Knowledge Layer**
    ---
    - GraphBuilder, TemporalGraphBuilder
    - Entity resolution and deduplication
    - Conflict detection and resolution

-   :material-book-open-variant: **Ontology Layer**
    ---
    - OntologyGenerator, SchemaValidator
    - OWL and RDF support
    - Automated hierarchy generation

-   :material-shield-check: **Quality Layer**
    ---
    - ConflictDetector, QualityScorer
    - Provenance tracking
    - Validation and verification

</div>

### Advanced: Orchestration Option

<div class="admonition tip" markdown>
<div class="admonition-title" markdown>**For Complex Workflows**</div>

For complex workflows, you can also use the `Semantica` class for orchestration. See the [Core Module](reference/core.md) documentation for details on advanced pipeline orchestration and parallel processing.

</div>

---

## ⏭️ Next Steps

### 🍳 Interactive Tutorials (Cookbook)

Get hands-on experience with these interactive Jupyter notebooks:

<div class="grid cards" markdown>

-   :material-school: **Welcome to Semantica**
    ---
    Comprehensive introduction to all Semantica modules and architecture
    - **Topics**: Framework overview, all modules, configuration
    - **Difficulty**: Beginner
    - **Time**: 30-45 minutes

-   :material-graph: **Your First Knowledge Graph**
    ---
    Build your first knowledge graph from a document
    - **Topics**: Entity extraction, relationship extraction, graph construction
    - **Difficulty**: Beginner
    - **Time**: 20-30 minutes

-   :material-database-import: **Data Ingestion**
    ---
    Learn to ingest from multiple sources
    - **Topics**: File, web, feed, stream, database ingestion
    - **Difficulty**: Beginner
    - **Time**: 15-20 minutes

-   :material-file-document: **Document Parsing**
    ---
    Parse various document formats
    - **Topics**: PDF, DOCX, HTML, JSON parsing
    - **Difficulty**: Beginner
    - **Time**: 15-20 minutes

</div>

### 📚 Documentation

- **[Core Concepts](concepts.md)**: Deep dive into knowledge graphs, ontologies, and semantic reasoning
- **[API Reference](reference/core.md)**: Complete technical documentation for all modules
- **[Examples](examples.md)**: Real-world examples and use cases
- **[Cookbook](cookbook.md)**: Full list of interactive Jupyter notebooks

---
