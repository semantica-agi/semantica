---
title: "Use Cases"
description: "Real-world applications of Semantica across domains, with linked cookbook notebooks for each."
icon: "briefcase"
---

Semantica is purpose-built for environments where AI outputs must be explainable, auditable, and traceable. The use cases below span regulated industries, advanced research, and high-stakes operational domains — each with linked Jupyter notebooks you can run today.

## At a Glance

| Use Case | Domain | Difficulty | Estimated Time |
| -------- | ------ | ---------- | -------------- |
| Biomedical Knowledge Graphs | Healthcare | Intermediate | 1–2 hours |
| Financial Data Integration | Finance | Intermediate | 1–2 hours |
| Fraud Detection | Finance | Advanced | 2–3 hours |
| Blockchain Analytics | Finance | Intermediate | 1–2 hours |
| Cybersecurity Threat Intelligence | Security | Advanced | 2–3 hours |
| Criminal Network Analysis | Security / Intelligence | Intermediate | 1–2 hours |
| Intelligence Analysis Orchestrator | Intelligence | Intermediate | 1–2 hours |
| Supply Chain Optimization | Operations | Intermediate | 1–2 hours |
| Renewable Energy Management | Energy | Intermediate | 1–2 hours |
| GraphRAG | AI / LLM | Advanced | 1–2 hours |

**Difficulty levels:**

- **Beginner** — basic Semantica knowledge only, no domain expertise needed
- **Intermediate** — some domain knowledge helpful, uses 2–4 Semantica modules
- **Advanced** — domain expertise expected, uses advanced features (temporal graphs, multi-source pipelines, reasoning)

## Research & Science

### Biomedical Knowledge Graphs

Connect genes, proteins, drugs, and diseases from scientific literature and databases to accelerate drug discovery and understand disease mechanisms. Semantica's temporal graphs and provenance tracking make every fact in the knowledge base traceable to its source publication.

**Key modules:** `ingest` (PubMed RSS), `semantic_extract`, `kg`, `deduplication`, `context`

**Cookbooks:**

- [Drug Discovery Pipeline](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/biomedical/01_Drug_Discovery_Pipeline.ipynb) — PubMed RSS ingestion, entity-aware chunking, GraphRAG, vector similarity search
- [Genomic Variant Analysis](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/biomedical/02_Genomic_Variant_Analysis.ipynb) — bioRxiv RSS, temporal KGs, deduplication, pathway analysis

## Finance & Trading

### Financial Data Integration

Unify financial data from APIs, MCP servers, and real-time streams into a single queryable knowledge graph — with conflict detection when sources disagree and full provenance back to each data feed.

**Key modules:** `ingest` (API, MCP, stream), `normalize`, `kg`, `conflicts`, `provenance`

**Cookbook:** [Financial Data Integration (MCP)](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/finance/01_Financial_Data_Integration_MCP.ipynb) — Alpha Vantage API, MCP servers, seed data, real-time ingestion

### Fraud Detection

Detect complex fraud rings using temporal graphs and pattern detection over transaction, device, and user data. Temporal edges let you query: "what connections existed during this window?" — critical for reconstructing fraud timelines.

**Key modules:** `kg` (temporal), `conflicts`, `reasoning`, `visualization`

**Cookbook:** [Fraud Detection](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/finance/02_Fraud_Detection.ipynb) — temporal KGs, cycle detection, fraud pattern analysis

### Blockchain Analytics

Map transaction flows, analyze DeFi protocols, and detect illicit activity across wallet and exchange networks. Graph algorithms (centrality, community detection) surface high-risk actors that linear transaction analysis misses.

**Cookbooks:**

- [DeFi Protocol Intelligence](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/blockchain/01_DeFi_Protocol_Intelligence.ipynb)
- [Transaction Network Analysis](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/blockchain/02_Transaction_Network_Analysis.ipynb)

## Security & Intelligence

### Cybersecurity Threat Intelligence

Ingest threat feeds (CVE databases, security RSS), detect anomalies in streaming data, and build threat intelligence knowledge graphs for proactive defense. Real-time streaming ingestion with temporal provenance means every threat event is timestamped and traceable.

**Key modules:** `ingest` (stream, feed), `kg` (temporal), `context`, `reasoning`, `export`

**Cookbooks:**

- [Real-Time Anomaly Detection](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/cybersecurity/01_Real_Time_Anomaly_Detection.ipynb)
- [Threat Intelligence Hybrid RAG](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/cybersecurity/02_Threat_Intelligence_Hybrid_RAG.ipynb)

### Criminal Network Analysis

Build knowledge graphs from police reports, court records, and OSINT feeds to identify key players, communities, and suspicious patterns. Network centrality analysis (PageRank, betweenness) surfaces actors that text search alone would miss.

**Key modules:** `ingest`, `semantic_extract`, `kg`, `visualization` (community detection)

**Cookbook:** [Criminal Network Analysis](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/intelligence/01_Criminal_Network_Analysis.ipynb)

### Intelligence Analysis Orchestrator

Process multiple intelligence sources in parallel using an orchestrator-worker pipeline pattern with multi-source conflict detection and resolution. When sources disagree on the same fact, Semantica flags and resolves rather than silently discarding.

**Key modules:** `pipeline`, `ingest`, `conflicts`, `provenance`, `export`

**Cookbook:** [Intelligence Analysis Orchestrator-Worker](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/intelligence/02_Intelligence_Analysis_Orchestrator_Worker.ipynb)

## Industry & Operations

### Supply Chain Optimization

Map suppliers, logistics routes, inventory levels, and delivery relationships to identify bottlenecks and optimize global supply chains. Graph path-finding reveals indirect dependencies that spreadsheet analysis cannot.

**Key modules:** `ingest`, `kg`, `reasoning`, `visualization`, `export` (Parquet for analytics)

**Cookbook:** [Supply Chain Data Integration](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/supply_chain/01_Supply_Chain_Data_Integration.ipynb)

### Renewable Energy Management

Connect sensor data, weather forecasts, and maintenance logs to predict equipment failures and optimize grid operations. Temporal graphs let you track asset states over time and correlate maintenance events with performance degradation.

**Key modules:** `ingest` (stream, API), `kg` (temporal), `reasoning`, `visualization`

**Cookbook:** [Energy Market Analysis](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/renewable_energy/01_Energy_Market_Analysis.ipynb)

## Advanced AI Patterns

### GraphRAG (Graph-Augmented Generation)

Use knowledge graphs to retrieve precise, structured context for LLM responses — with hybrid retrieval (vector + graph traversal), logical inference, and source attribution on every claim. Every answer links back to a node in the graph, making hallucination auditable rather than invisible.

**Key modules:** `context`, `vector_store`, `kg`, `reasoning`, `llms`

**Cookbooks:**

- [GraphRAG Complete](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb) — production-ready implementation with hybrid retrieval
- [RAG vs. GraphRAG Comparison](https://github.com/semantica-agi/semantica/blob/main/cookbook/use_cases/advanced_rag/02_RAG_vs_GraphRAG_Comparison.ipynb) — side-by-side benchmark on real-world data

<CardGroup cols={3}>
  <Card title="Cookbook" icon="flask" href="cookbook">
    Full notebook catalog organized by topic and difficulty.
  </Card>
  <Card title="Modules Guide" icon="puzzle-piece" href="modules">
    Every module with code examples.
  </Card>
  <Card title="API Reference" icon="code" href="reference/context">
    Complete technical documentation.
  </Card>
</CardGroup>

<Info>
  Have a use case to add? [Open a PR](https://github.com/semantica-agi/semantica) or start a discussion on GitHub.
</Info>
