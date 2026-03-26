# Frequently Asked Questions

Common questions about Semantica. Use Ctrl+F to find what you need.

---

## General

### What is Semantica?

Semantica is an open-source framework for building context graphs and decision intelligence layers for AI. It transforms unstructured data — documents, APIs, databases — into structured knowledge graphs with full provenance tracking, making AI systems explainable and auditable.

### What can I build with Semantica?

- Knowledge graphs from documents and multi-source data
- GraphRAG systems with graph-grounded retrieval
- AI agents with structured decision history and semantic memory
- Compliance-ready pipelines with W3C PROV-O lineage

### What makes Semantica different from other frameworks?

Most frameworks stop at retrieval or generation. Semantica adds an **accountability layer**: every decision is recorded, every fact links to a source, and every reasoning step is explainable. It's designed for environments where you need to audit why an AI reached a conclusion.

### Is Semantica free?

Yes — MIT licensed, no vendor lock-in. Some features require third-party API keys (e.g., OpenAI embeddings), but Semantica itself is free.

---

## Installation

### How do I install Semantica?

```bash
pip install semantica
```

See [Installation](installation.md) for virtual environment setup, optional extras, and troubleshooting.

### What Python version do I need?

Python 3.8 or higher. Python 3.11+ is recommended for best performance.

### What are the system requirements?

- Python 3.8+
- 4 GB RAM minimum; 16 GB+ recommended for larger graphs
- Optional GPU for embedding generation and ML inference

---

## Getting Started

### Where do I start?

1. [Installation](installation.md) — get set up
2. [Getting Started](getting-started.md) — core concepts and first example
3. [Quickstart Tutorial](quickstart.md) — full step-by-step pipeline
4. [Cookbook](cookbook.md) — interactive Jupyter notebooks

### What data sources does Semantica support?

- **Files** — PDF, DOCX, HTML, JSON, CSV, Excel, PPTX, archives
- **Web** — crawl with `WebIngestor`, RSS feeds
- **Databases** — PostgreSQL, MySQL, Snowflake via `DBIngestor` / `SnowflakeIngestor`
- **Streams** — Kafka, real-time ingestion
- **Media** — image OCR, audio/video metadata

---

## Features

### Can I use my own models?

Yes. Semantica supports custom entity extraction models, embedding models, LLM providers (via LiteLLM — 100+ models), and custom pipeline processors.

### Does Semantica support GPUs?

Yes. When available, GPUs are used automatically for embedding generation, ML model inference, and vector operations. Install `semantica[gpu]` for CUDA support.

### How does Semantica handle large datasets?

- **Batching** — process documents in configurable chunks
- **Parallel processing** — `PipelineBuilder` supports configurable worker counts
- **Delta processing** — update graphs incrementally without full recompute
- **Graph backends** — swap in-memory NetworkX for Neo4j, FalkorDB, or Apache AGE at scale

---

## Technical

### What graph databases are supported?

Neo4j, FalkorDB, Apache AGE (PostgreSQL), Amazon Neptune, and in-memory NetworkX for development.

### What export formats are available?

RDF (Turtle, JSON-LD, N-Triples, XML), Apache Parquet, ArangoDB AQL, CSV, YAML, and OWL ontologies.

### Is Semantica production-ready?

Yes. v0.3.0 ships with 886+ passing tests, `PipelineValidator`, `FailureHandler` with exponential backoff, W3C PROV-O provenance, and change management with checksums. See [What's New](index.md#whats-new-in-v030) for details.

---

## Troubleshooting

### Import error: `ModuleNotFoundError: No module named 'semantica'`

Ensure you have the correct Python environment active, then:

```bash
pip list | grep semantica
pip install --upgrade semantica
```

### Installation fails with dependency errors

```bash
pip install --upgrade pip wheel
pip install semantica
```

### Memory errors during processing

Reduce batch sizes, enable streaming ingestion, or switch to a persistent graph backend (Neo4j, FalkorDB).

### Slow embedding or inference

Install GPU support (`pip install semantica[gpu]`) and ensure CUDA is available on your system.

---

## Support

### Where can I get help?

- [Discord](https://discord.gg/sV34vps5hH) — community chat and support
- [GitHub Issues](https://github.com/Hawksight-AI/semantica/issues) — bug reports and feature requests
- [GitHub Discussions](https://github.com/Hawksight-AI/semantica/discussions) — questions and ideas

### How do I report a bug?

1. Search [existing issues](https://github.com/Hawksight-AI/semantica/issues) first
2. Open a new issue with: description, reproduction steps, expected vs actual behavior, and your environment (Python version, OS, Semantica version)

### How do I contribute?

See the [Contributing Guide](contributing.md).
