# Getting Started

**Semantica** is the context and intelligence layer for AI — turning raw data into explainable, auditable knowledge graphs for high-stakes domains.

!!! tip "Just here for code?"
    Jump straight to the [Quick Start](#quick-start) or explore the [Cookbook](cookbook.md) for interactive notebooks.

---

## What You Can Build

- **GraphRAG Systems** — enhanced retrieval with semantic graph reasoning
- **AI Agents** — accountable agents with structured decision history and memory
- **Knowledge Graphs** — production-ready semantic knowledge bases
- **Compliance-Ready AI** — auditable systems with full W3C PROV-O provenance

---

## Installation

```bash
pip install semantica
```

With all optional dependencies:

```bash
pip install semantica[all]
```

Verify:

```python
import semantica
print(semantica.__version__)
```

---

## Quick Start

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
    scenario="Choose LLM for production pipeline",
    reasoning="GPT-4 benchmark advantage justifies cost increase",
    outcome="selected_gpt4",
    confidence=0.91,
)

# Find similar past decisions
precedents = context.find_precedents("model selection", limit=5)
```

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

- [Core Concepts](concepts.md) — knowledge graphs, ontologies, reasoning explained
- [Quickstart Tutorial](quickstart.md) — build a full pipeline step by step
- [Cookbook](cookbook.md) — 14 domain-specific Jupyter notebook tutorials
- [API Reference](reference/core.md) — complete module documentation

---

## Help

- [Discord Community](https://discord.gg/sV34vps5hH) — ask questions, share projects
- [GitHub Issues](https://github.com/Hawksight-AI/semantica/issues) — report bugs or request features
- [FAQ](faq.md) — common questions answered
