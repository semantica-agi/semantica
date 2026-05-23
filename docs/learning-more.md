---
title: "Learning More"
description: "Structured learning paths, configuration reference, troubleshooting, and performance guidance."
icon: "graduation-cap"
---

Whether you're running your first pipeline or deploying Semantica in production, this page gives you a structured path forward — from beginner to enterprise-grade usage.

## Learning Paths

<CardGroup cols={3}>
  <Card title="Beginner (1–2 hrs)" icon="seedling">
    New to Semantica and knowledge graphs.
    [Start with Installation →](installation)
  </Card>
  <Card title="Intermediate (4–6 hrs)" icon="compass">
    Comfortable with basics, building real applications.
    [Start with Modules →](modules)
  </Card>
  <Card title="Advanced (8+ hrs)" icon="rocket">
    Enterprise deployments, customization, and extension.
    [Start with Architecture →](architecture)
  </Card>
</CardGroup>

### Beginner Path

1. [Installation Guide](installation) — set up your environment
2. [Core Concepts](concepts) — understand KGs, embeddings, and extraction
3. [Getting Started](getting-started) — first working example
4. [Quickstart Tutorial](quickstart) — build your first knowledge graph
5. [Welcome to Semantica notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/01_Welcome_to_Semantica.ipynb) — interactive introduction to all modules

### Intermediate Path

1. [Modules Guide](modules) — every module with code examples
2. [Building Knowledge Graphs notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/07_Building_Knowledge_Graphs.ipynb)
3. [Embeddings notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/09_Embeddings.ipynb)
4. [GraphRAG Complete notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb)
5. [Multi-Source Data Integration notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/06_Multi_Source_Data_Integration.ipynb)
6. [Use Cases](use-cases) — domain-specific examples with notebooks

### Advanced Path

1. [Architecture Guide](architecture) — three-layer system, extension points, design decisions
2. [Temporal Graphs notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/04_Temporal_Graphs.ipynb) — v0.4.0 temporal intelligence
3. [Ontology notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/14_Ontology.ipynb) — v0.5.0 Ontology Hub
4. [Complete Visualization Suite notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/03_Complete_Visualization_Suite.ipynb)
5. [Multi-Format Export notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/05_Multi_Format_Export.ipynb)

## Configuration Reference

All settings can be overridden with environment variables — no code changes needed.

| Setting | Environment Variable | Default |
| ------- | -------------------- | ------- |
| OpenAI API Key | `OPENAI_API_KEY` | `None` |
| Groq API Key | `GROQ_API_KEY` | `None` |
| Anthropic API Key | `ANTHROPIC_API_KEY` | `None` |
| Embedding Provider | `SEMANTICA_EMBEDDING_PROVIDER` | `"openai"` |
| Graph Backend | `SEMANTICA_GRAPH_BACKEND` | `"networkx"` |
| Log Level | `SEMANTICA_LOG_LEVEL` | `"INFO"` |
| Log Format | `SEMANTICA_LOG_FORMAT` | `"text"` |

## Troubleshooting

### `ModuleNotFoundError: No module named 'semantica'`

Verify installation and that the correct Python environment is active:

```bash
pip list | grep semantica
pip install --upgrade semantica
```

For optional features, install the relevant extra:

```bash
pip install "semantica[llm-openai]"   # OpenAI provider
pip install "semantica[gpu]"          # GPU acceleration
```

### `AuthenticationError`

Set your API key as an environment variable — never hardcode keys in source files:

```bash
export OPENAI_API_KEY="sk-..."
export GROQ_API_KEY="gsk_..."
```

### `MemoryError` or OOM crashes

Switch from the default in-memory NetworkX backend to a persistent graph database:

```python
from semantica.graph_store import FalkorDBStore
from semantica.kg import GraphBuilder

store   = FalkorDBStore(host="localhost", port=6379)
builder = GraphBuilder(merge_entities=True, graph_store=store)
```

Also reduce batch sizes and enable streaming ingestion for large corpora.

### Slow processing on large datasets

Enable parallel execution and GPU acceleration:

```python
from semantica.pipeline import Pipeline

pipeline = Pipeline(workers=8, batch_size=32)
pipeline.run(sources)
```

```bash
pip install "semantica[gpu]"  # CUDA-backed embeddings
```

### Windows `[all]` installation fails

Fixed in **v0.5.0**. Upgrade:

```bash
pip install --upgrade semantica
```

Or install extras individually: `pip install "semantica[core]"`, then add `[llm-openai]`, `[gpu]`, etc. as needed.

### cp1252 encoding crash on Windows

Fixed in **v0.5.0**. For earlier versions, pass encoding explicitly or set the environment variable:

```bash
set PYTHONIOENCODING=utf-8
```

## Performance Optimization

### Backend Selection

| Operation | NetworkX (default) | Neo4j / FalkorDB |
| --------- | ------------------ | ---------------- |
| Graph construction | Fast | Moderate |
| Query performance | Moderate | Fast |
| Scalability | Low — in-memory only | High — persistent |
| Recommended for | Development, small graphs | Production, large corpora |

Use NetworkX for local development and prototyping. Switch to a persistent backend before deploying to production.

### Batch Processing

Process documents in batches rather than one at a time. Configure `chunk_size` based on available RAM — a good starting point is 1,000 documents per batch on a 16 GB machine.

### Deduplication v2

If deduplication is a bottleneck, switch from v1 strategies to v2:

```python
resolver = EntityResolver()
merged   = resolver.resolve(entities, strategy="semantic_v2")  # up to 7x faster
```

## Security Best Practices

- **API keys** — store in environment variables or a secrets manager; never commit them to version control; rotate on a schedule
- **Sensitive data** — use local embedding models (Ollama, HuggingFace) for PII or classified content; avoid sending sensitive data to external APIs without data handling agreements
- **Graph exports** — encrypt sensitive exports at rest; use the v0.5.0 SSRF-safe `base_url` validation when configuring custom LLM gateways
- **XML ingestion** — always use `XMLIngestor` (v0.5.0), which uses the XXE-safe lxml backend; never parse untrusted XML with the standard library parser

<CardGroup cols={2}>
  <Card title="Cookbook" icon="flask" href="cookbook">
    Interactive Jupyter notebooks from beginner to advanced.
  </Card>
  <Card title="FAQ" icon="circle-question" href="faq">
    Common questions answered.
  </Card>
  <Card title="API Reference" icon="code" href="reference/core">
    Complete technical documentation.
  </Card>
  <Card title="Use Cases" icon="briefcase" href="use-cases">
    Domain-specific examples with notebooks.
  </Card>
</CardGroup>
