# Use Cases

Real-world applications of Semantica across domains, with linked cookbook notebooks for each.

---

## Overview

| Use Case | Domain | Difficulty | Estimated Time |
|----------|--------|------------|----------------|
| Biomedical Knowledge Graphs | Healthcare | Intermediate | 1–2 hours |
| Financial Data Integration | Finance | Intermediate | 1–2 hours |
| Fraud Detection | Finance | Advanced | 2–3 hours |
| Blockchain Analytics | Finance | Intermediate | 1–2 hours |
| Cybersecurity Threat Intelligence | Security | Advanced | 2–3 hours |
| Criminal Network Analysis | Security / Intelligence | Intermediate | 1–2 hours |
| Intelligence Analysis Orchestrator | Intelligence | Intermediate | 1–2 hours |
| Supply Chain Optimization | Operations | Intermediate | 1–2 hours |
| Renewable Energy Management | Energy | Intermediate | 1–2 hours |
| GraphRAG | AI | Advanced | 1–2 hours |

**Difficulty levels**:

- **Beginner** — basic Semantica knowledge only
- **Intermediate** — some domain knowledge helpful
- **Advanced** — domain expertise + advanced Semantica features

---

## Research & Science

### Biomedical Knowledge Graphs

Connect genes, proteins, drugs, and diseases from scientific literature and databases to accelerate drug discovery and understand disease pathways.

**Cookbooks**:
- [Drug Discovery Pipeline](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/biomedical/01_Drug_Discovery_Pipeline.ipynb) — PubMed RSS ingestion, entity-aware chunking, GraphRAG, vector similarity search
- [Genomic Variant Analysis](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/biomedical/02_Genomic_Variant_Analysis.ipynb) — bioRxiv RSS, temporal KGs, deduplication, pathway analysis

---

## Finance & Trading

### Financial Data Integration

Unify financial data from APIs, MCP servers, and real-time streams into a single queryable knowledge graph.

**Cookbook**: [Financial Data Integration (MCP)](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/finance/01_Financial_Data_Integration_MCP.ipynb) — Alpha Vantage API, MCP servers, seed data, real-time ingestion

### Fraud Detection

Detect complex fraud rings using temporal graphs and pattern detection over transaction, device, and user data.

**Cookbook**: [Fraud Detection](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/finance/02_Fraud_Detection.ipynb) — temporal KGs, cycle detection, fraud pattern analysis

### Blockchain Analytics

Map transaction flows, analyze DeFi protocols, and detect illicit activity across wallet and exchange networks.

**Cookbooks**:
- [DeFi Protocol Intelligence](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/blockchain/01_DeFi_Protocol_Intelligence.ipynb)
- [Transaction Network Analysis](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/blockchain/02_Transaction_Network_Analysis.ipynb)

---

## Security & Intelligence

### Cybersecurity Threat Intelligence

Ingest threat feeds (CVE databases, security RSS), detect anomalies in streaming data, and build threat intelligence knowledge graphs for proactive defense.

**Cookbooks**:
- [Real-Time Anomaly Detection](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/cybersecurity/01_Real_Time_Anomaly_Detection.ipynb)
- [Threat Intelligence Hybrid RAG](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/cybersecurity/02_Threat_Intelligence_Hybrid_RAG.ipynb)

### Criminal Network Analysis

Build knowledge graphs from police reports, court records, and OSINT feeds to identify key players, communities, and suspicious patterns using network centrality analysis.

**Cookbook**: [Criminal Network Analysis](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/intelligence/01_Criminal_Network_Analysis.ipynb)

### Intelligence Analysis Orchestrator

Process multiple intelligence sources in parallel using an orchestrator-worker pipeline pattern with multi-source conflict detection and integration.

**Cookbook**: [Intelligence Analysis Orchestrator-Worker](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/intelligence/02_Intelligence_Analysis_Orchestrator_Worker.ipynb)

---

## Industry & Operations

### Supply Chain Optimization

Map suppliers, logistics routes, and inventory levels to identify bottlenecks and optimize global supply chains.

**Cookbook**: [Supply Chain Data Integration](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/supply_chain/01_Supply_Chain_Data_Integration.ipynb)

### Renewable Energy Management

Connect sensor data, weather forecasts, and maintenance logs to predict equipment failures and optimize grid operations.

**Cookbook**: [Energy Market Analysis](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/renewable_energy/01_Energy_Market_Analysis.ipynb)

---

## Advanced AI Patterns

### GraphRAG (Graph-Augmented Generation)

Use knowledge graphs to retrieve precise, structured context for LLM responses — with hybrid retrieval, logical inference, and source attribution.

**Cookbooks**:
- [GraphRAG Complete](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb) — production-ready implementation
- [RAG vs. GraphRAG Comparison](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/02_RAG_vs_GraphRAG_Comparison.ipynb) — side-by-side comparison

---

## Next Steps

- [Cookbook](cookbook.md) — full notebook catalog organized by topic and difficulty
- [Modules Guide](modules.md) — every module with examples
- [API Reference](reference/core.md) — complete technical documentation

!!! info "Have a use case to add?"
    [Open a PR](https://github.com/Hawksight-AI/semantica) or start a discussion on GitHub.
