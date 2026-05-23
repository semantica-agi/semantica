---
title: "Community Projects"
description: "Projects, extensions, and integrations built by the Semantica community."
icon: "people-group"
---

<Tip>
  Building something with Semantica? [Submit it on GitHub](https://github.com/semantica-agi/semantica/issues/new?template=community_project.md) — we'd love to feature it here.
</Tip>

Semantica is used across academia, enterprise, and independent research. Below is a snapshot of the ecosystem being built by the community.

## Projects Using Semantica

### Research & Academia

Teams in academia are using Semantica to build structured, auditable knowledge from unstructured scientific literature.

- **Academic literature mapping** — citation graph construction across multi-year corpora with temporal provenance
- **Biomedical knowledge graphs** — connecting genes, proteins, drugs, and diseases from PubMed and preprint feeds
- **Social network analysis** — community detection and influence analysis over entity-linked interaction graphs
- **Computational linguistics** — coreference resolution pipelines with entity-linked output for downstream NLP tasks

### Enterprise & Industry

Production deployments span regulated and high-stakes industries where AI accountability is not optional.

- **Business intelligence** — corporate knowledge bases built from filings, reports, and internal documentation
- **Cybersecurity & threat intelligence** — adversary attribution graphs, CVE-linked threat feeds, incident timelines
- **Healthcare & clinical AI** — patient safety graphs, drug interaction knowledge bases, HIPAA-compliant audit trails
- **Financial services** — fraud detection graphs, regulatory compliance pipelines (SOX/GDPR/MiFID II), risk lineage
- **Legal & compliance** — contract analysis pipelines, regulatory change tracking, evidence-backed research graphs
- **Critical infrastructure** — supply chain risk graphs, energy grid event graphs, logistics provenance

### Independent & Open Source

- **GraphRAG toolkits** — custom retrieval layers built on top of Semantica's `context` + `vector_store` modules
- **Domain-specific extractors** — NER and relation extractors for clinical, legal, and scientific text
- **Temporal graph dashboards** — visual timelines built with Semantica's `TemporalKnowledgeGraph` + custom visualization adapters

## Supported Integrations

### Vector Databases

- FAISS — in-process, CPU/GPU
- Pinecone — managed vector cloud
- Weaviate — schema-first hybrid search
- Qdrant — high-performance Rust-native
- Milvus — enterprise-scale distributed
- PgVector — Postgres-native for SQL stacks

### Graph Databases

- Neo4j — industry standard, Cypher query
- FalkorDB — Redis-protocol, low-latency
- Apache AGE — PostgreSQL extension, OpenCypher
- Amazon Neptune — managed AWS, SPARQL + Gremlin

### LLM Providers

- OpenAI (GPT-4o, GPT-4, GPT-3.5)
- Anthropic (Claude Opus, Sonnet, Haiku)
- Google Gemini
- Groq (LLaMA, Mixtral — fast inference)
- Ollama (fully local, air-gapped)
- HuggingFace
- DeepSeek
- Novita AI
- LiteLLM (100+ model gateway)

### NLP Libraries

- spaCy — production NER and dependency parsing
- NLTK — tokenization and feature extraction
- Sentence Transformers — semantic embeddings
- FastEmbed — lightweight, fast inference

## Community Extensions

The plugin system (`PluginRegistry`) makes it easy to add new capabilities without touching core code. The community has built:

- **Custom entity extractors** — domain-specific NER for clinical entities, legal clause types, and financial instruments
- **Export adapters** — specialized serialization formats for proprietary industry systems
- **Ingestor plugins** — adapters for SharePoint, Notion, Confluence, and custom databases
- **Visualization plugins** — enhanced dashboards with Plotly, D3.js, and custom graph renderers
- **Evaluation harnesses** — domain-specific precision/recall benchmarks using `semantica.evals`

## Build Your Own Extension

Any Semantica component can be extended via the registry pattern:

```python
from semantica.ingest.registry import method_registry

def my_ingestor(source):
    return [{"text": "...", "metadata": {}, "source": source}]

method_registry.register("file", "my_format", my_ingestor)
```

See [Architecture](architecture#extension-points) for the full extension guide.

## How to Contribute

<CardGroup cols={2}>
  <Card title="Contributing Guide" icon="code-pull-request" href="contributing-guide">
    Submit code, documentation, tests, or cookbook notebooks.
  </Card>
  <Card title="GitHub Issues" icon="circle-dot" href="https://github.com/semantica-agi/semantica/issues">
    Report bugs, request features, or propose integrations.
  </Card>
  <Card title="Discord" icon="discord" href="https://discord.gg/sV34vps5hH">
    Share what you're building with the community.
  </Card>
  <Card title="GitHub Discussions" icon="comments" href="https://github.com/semantica-agi/semantica/discussions">
    Long-form questions, design discussions, and ideas.
  </Card>
</CardGroup>
