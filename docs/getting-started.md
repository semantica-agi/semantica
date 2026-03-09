# Getting Started

## Overview

**Semantica** is a semantic intelligence layer that bridges the gap between raw data and trustworthy AI. It transforms unstructured data into explainable, auditable knowledge graphs perfect for high-stakes domains.

### What You Can Build
- **GraphRAG Systems** - Enhanced retrieval with semantic reasoning
- **AI Agents** - Trustworthy agents with explainable memory
- **Knowledge Graphs** - Production-ready semantic databases
- **Compliance-Ready AI** - Auditable systems with full provenance

---

## Installation

```bash
pip install semantica
```

Or with all features:

```bash
pip install semantica[all]
```

Verify installation:

```python
import semantica
print(f"Semantica {semantica.__version__} installed!")
```

---

## Quick Start

```python
from semantica.semantic_extract import NERExtractor
from semantica.kg import GraphBuilder

# Extract entities
ner = NERExtractor(method="ml", model="en_core_web_sm")
entities = ner.extract("Apple Inc. was founded by Steve Jobs in 1976.")

# Build knowledge graph
kg = GraphBuilder().build({"entities": entities, "relationships": []})
print(f"Built KG with {len(kg.get('entities', []))} entities")
```

**What this does:**
- Extracts entities (people, organizations, dates) from text
- Builds a knowledge graph from extracted entities
- Outputs the number of entities found

---

## Core Architecture

Semantica uses a **modular architecture** - use only what you need:

### 1️⃣ Input Layer - Data Ingestion
```python
from semantica.ingest import FileIngestor
documents = FileIngestor().ingest_directory("docs/")
```

### 2️⃣ Semantic Layer - Intelligence Engine
```python
from semantica.semantic_extract import NERExtractor, RelationExtractor
entities = NERExtractor().extract(text)
relationships = RelationExtractor().extract(text, entities)
```

### 3️⃣ Output Layer - Knowledge Assets
```python
from semantica.kg import GraphBuilder
kg = GraphBuilder().build_graph(entities, relationships)
```

---

## Next Steps

### 🍳 Interactive Tutorials
1. **[Welcome to Semantica](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/01_Welcome_to_Semantica.ipynb)** - Complete framework overview
2. **[Your First Knowledge Graph](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/08_Your_First_Knowledge_Graph.ipynb)** - Hands-on graph building
3. **[GraphRAG Complete](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb)** - Production-ready RAG

### 📚 Learn More
- **[Core Concepts](concepts.md)** - Deep dive into knowledge graphs & ontologies
- **[Cookbook](cookbook.md)** - 14 domain-specific tutorials
- **[API Reference](reference/core.md)** - Complete technical documentation

---

## Need Help?

- **[💬 Discord Community](https://discord.gg/sV34vps5hH)** - Get help from the community
- **[🐛 Issues](https://github.com/Hawksight-AI/semantica/issues)** - Report bugs or request features
- **[📖 Documentation](https://semantica.readthedocs.io/)** - Full documentation site
