# Semantica Cookbook

Interactive Jupyter notebooks covering everything from your first knowledge graph to production GraphRAG systems.

!!! tip "Where to start"
    - **New to Semantica** — begin with [Core Tutorials](#core-tutorials)
    - **Building an application** — see [Advanced Concepts](#advanced-concepts) or [Industry Use Cases](#industry-use-cases)
    - **Need installation help** — see the [Installation Guide](installation.md)

!!! note "Prerequisites"
    Python 3.8+, Jupyter, and an OpenAI API key (for most examples).

---

## Featured Recipes

<div class="grid cards" markdown>

-   :material-graph: **Your First Knowledge Graph**
    ---
    Go from raw text to a queryable knowledge graph in 20 minutes.

    **Topics**: Extraction, Graph Construction, Visualization · **Difficulty**: Beginner

    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/08_Your_First_Knowledge_Graph.ipynb)

-   :material-robot: **GraphRAG Complete**
    ---
    Build a production-ready Graph Retrieval Augmented Generation system with hybrid retrieval and logical inference.

    **Topics**: RAG, LLMs, Vector Search, Graph Traversal · **Difficulty**: Advanced

    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb)

-   :material-scale-balance: **RAG vs. GraphRAG Comparison**
    ---
    Side-by-side benchmark of standard RAG vs. GraphRAG on real-world data.

    **Topics**: RAG, GraphRAG, Benchmarking, Reasoning Gap · **Difficulty**: Intermediate

    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/02_RAG_vs_GraphRAG_Comparison.ipynb)

-   :material-shield-alert: **Real-Time Anomaly Detection**
    ---
    Detect anomalies in streaming data using dynamic knowledge graphs.

    **Topics**: Streaming, Security, Dynamic Graphs · **Difficulty**: Advanced

    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/cybersecurity/01_Real_Time_Anomaly_Detection.ipynb)

</div>

---

## Core Tutorials {#core-tutorials}

Essential guides to master the Semantica framework.

<div class="grid cards" markdown>

-   :material-hand-wave: **Welcome to Semantica**
    ---
    An interactive introduction to the framework's core philosophy and all modules including ingestion, parsing, extraction, knowledge graphs, embeddings, and more.
    
    **Topics**: Framework Overview, Architecture, All Modules
    
    **Difficulty**: Beginner
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/01_Welcome_to_Semantica.ipynb)

-   :material-database-import: **Data Ingestion**
    ---
    Techniques for loading data from multiple sources using FileIngestor, WebIngestor, FeedIngestor, StreamIngestor, RepoIngestor, EmailIngestor, DBIngestor, and MCPIngestor.
    
    **Topics**: File Ingestion, Web Scraping, Database Integration, Streams, Feeds, Repositories, Email, MCP
    
    **Difficulty**: Beginner
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/02_Data_Ingestion.ipynb)

-   :material-file-document-outline: **Document Parsing**
    ---
    Extracting clean text from complex formats like PDF, DOCX, and HTML.
    
    **Topics**: OCR, PDF Parsing, Text Extraction
    
    **Difficulty**: Beginner
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/03_Document_Parsing.ipynb)

-   :material-broom: **Data Normalization**
    ---
    Pipelines for cleaning, normalizing, and preparing text.
    
    **Topics**: Text Cleaning, Unicode, Formatting
    
    **Difficulty**: Beginner
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/04_Data_Normalization.ipynb)

-   :material-account-search: **Entity Extraction**
    ---
    Using NER to identify people, organizations, and custom entities.
    
    **Topics**: NER, Spacy, LLM Extraction
    
    **Difficulty**: Beginner
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/05_Entity_Extraction.ipynb)

-   :material-relation-many-to-many: **Relation Extraction**
    ---
    Discovering and classifying relationships between entities.
    
    **Topics**: Relation Classification, Dependency Parsing
    
    **Difficulty**: Beginner
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/06_Relation_Extraction.ipynb)

-   :material-vector-square: **Embedding Generation**
    ---
    Creating and managing vector embeddings for semantic search.
    
    **Topics**: Embeddings, OpenAI, HuggingFace
    
    **Difficulty**: Intermediate
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/12_Embedding_Generation.ipynb)

-   :material-database-search: **Vector Store**
    ---
    Setting up vector stores for similarity search and retrieval.
    
    **Difficulty**: Intermediate
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/13_Vector_Store.ipynb)

-   :material-database-settings: **Graph Store**
    ---
    Persisting knowledge graphs in Neo4j or FalkorDB.
    
    **Topics**: Neo4j, Cypher, Persistence
    
    **Difficulty**: Intermediate
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/09_Graph_Store.ipynb)

-   :material-sitemap: **Ontology**
    ---
    Defining domain schemas and ontologies to structure your data.
    
    **Topics**: OWL, RDF, Schema Design
    
    **Difficulty**: Intermediate
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/14_Ontology.ipynb)

</div>

---

## Advanced Concepts

Deep dive into advanced features, customization, and complex workflows.

<div class="grid cards" markdown>

-   :material-flask: **Advanced Extraction**
    ---
    Custom extractors, LLM-based extraction, and complex pattern matching.
    
    **Topics**: Custom Models, Regex, LLMs
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/01_Advanced_Extraction.ipynb)

-   :material-chart-network: **Advanced Graph Analytics**
    ---
    Centrality, community detection, and pathfinding algorithms.
    
    **Topics**: PageRank, Louvain, Shortest Path
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/02_Advanced_Graph_Analytics.ipynb)

-   :material-brain: **Advanced Context Engineering**
    ---
    Build a production-grade memory system for AI agents using persistent Vector (FAISS) and Graph (Neo4j) stores.
    
    **Topics**: Agent Memory, GraphRAG, Entity Injection, Lifecycle Management
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/11_Advanced_Context_Engineering.ipynb)

-   :material-monitor-dashboard: **Complete Visualization Suite**
    ---
    Creating interactive, publication-ready visualizations of your graphs.
    
    **Topics**: PyVis, NetworkX, D3.js
    
    **Difficulty**: Intermediate
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/03_Complete_Visualization_Suite.ipynb)

-   :material-scale-balance: **Conflict Resolution**
    ---
    Strategies for handling contradictory information from multiple sources.
    
    **Topics**: Truth Discovery, Voting, Confidence
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/17_Conflict_Detection_and_Resolution.ipynb)

-   :material-export: **Multi-Format Export**
    ---
    Exporting to RDF, OWL, JSON-LD, and NetworkX formats.
    
    **Topics**: Serialization, Interoperability
    
    **Difficulty**: Intermediate
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/05_Multi_Format_Export.ipynb)

-   :material-source-merge: **Multi-Source Integration**
    ---
    Merging data from disparate sources into a unified graph.
    
    **Topics**: Entity Resolution, Merging, Fusion
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/06_Multi_Source_Data_Integration.ipynb)

-   :material-pipe: **Pipeline Orchestration**
    ---
    Building robust, automated data processing pipelines.
    
    **Topics**: Workflows, Automation, Error Handling
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/07_Pipeline_Orchestration.ipynb)

-   :material-brain: **Reasoning and Inference**
    ---
    Using logical reasoning to infer new knowledge from existing facts.
    
    **Topics**: Logic Rules, Inference Engines
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/08_Reasoning_and_Inference.ipynb)
-   :material-layers: **Semantic Layer Construction**
    ---
    Building a semantic layer over your data warehouse or lake.
    
    **Topics**: Semantic Layer, Data Warehouse
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/09_Semantic_Layer_Construction.ipynb)

-   :material-clock-outline: **Temporal Knowledge Graphs**
    ---
    Modeling and querying data that changes over time.
    
    **Topics**: Time Series, Temporal Logic
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/10_Temporal_Knowledge_Graphs.ipynb)

</div>

---

## Industry Use Cases {#industry-use-cases}

Real-world examples and end-to-end applications across various industries.

### Biomedical

<div class="grid cards" markdown>

-   :material-pill: **Drug Discovery Pipeline**
    ---
    Accelerating drug discovery by connecting genes, proteins, and drugs using PubMed RSS feeds, entity-aware chunking, GraphRAG, and vector similarity search.
    
    **Topics**: Bioinformatics, KG Construction, GraphRAG, Vector Search
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/biomedical/01_Drug_Discovery_Pipeline.ipynb)

-   :material-dna: **Genomic Variant Analysis**
    ---
    Analyzing genomic variants and their implications for disease using bioRxiv RSS feeds, temporal knowledge graphs, deduplication, and pathway analysis.
    
    **Topics**: Genomics, Variant Calling, Temporal KGs, Graph Analytics
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/biomedical/02_Genomic_Variant_Analysis.ipynb)

</div>

### Finance

<div class="grid cards" markdown>

-   :material-finance: **Financial Data Integration MCP**
    ---
    Merging financial data from Alpha Vantage API, MCP servers, RSS feeds, and market feeds with seed data integration.
    
    **Topics**: Finance, Data Fusion, MCP Integration, Real-Time Ingestion
    
    **Difficulty**: Intermediate
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/finance/01_Financial_Data_Integration_MCP.ipynb)

-   :material-incognito: **Fraud Detection**
    ---
    Identifying fraudulent activities and patterns in transaction networks using temporal knowledge graphs, conflict detection, and pattern recognition.
    
    **Topics**: Anomaly Detection, Graph Mining, Temporal Analysis, Pattern Detection
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/finance/02_Fraud_Detection.ipynb)

</div>

### Blockchain

<div class="grid cards" markdown>

-   :material-bitcoin: **DeFi Protocol Intelligence**
    ---
    Analyzing decentralized finance protocols and transaction flows using CoinDesk RSS feeds, ontology-aware chunking, conflict detection, and ontology generation.
    
    **Topics**: Blockchain, DeFi, Smart Contracts, Ontology, Conflict Resolution
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/blockchain/01_DeFi_Protocol_Intelligence.ipynb)

-   :material-network: **Transaction Network Analysis**
    ---
    Mapping and analyzing blockchain transaction networks using blockchain APIs, deduplication, and network pattern detection.
    
    **Topics**: Blockchain Analytics, Network Analysis, Deduplication, Pattern Detection
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/blockchain/02_Transaction_Network_Analysis.ipynb)

</div>

### Cybersecurity

<div class="grid cards" markdown>

-   :material-shield-alert: **Real-Time Anomaly Detection**
    ---
    Detecting anomalies in real-time network traffic streams using CVE RSS feeds, Kafka streams, temporal knowledge graphs, and sentence chunking.
    
    **Topics**: Network Security, Streaming, Temporal KGs, Pattern Detection
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/cybersecurity/01_Real_Time_Anomaly_Detection.ipynb)

-   :material-robot-angry: **Threat Intelligence Hybrid RAG**
    ---
    Combining enhanced GraphRAG with threat intelligence for security insights using security RSS feeds, entity-aware chunking, deduplication, and temporal knowledge graphs.
    
    **Topics**: Threat Intelligence, GraphRAG, Security, Hybrid Retrieval
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/cybersecurity/02_Threat_Intelligence_Hybrid_RAG.ipynb)

</div>

### Intelligence

<div class="grid cards" markdown>

-   :material-account-network: **Criminal Network Analysis**
    ---
    Analyze criminal networks with graph analytics and key player detection using OSINT RSS feeds, deduplication, and network centrality analysis.
    
    **Topics**: Forensics, Social Network Analysis, Deduplication, Graph Analytics
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/intelligence/01_Criminal_Network_Analysis.ipynb)

-   :material-file-search: **Intelligence Analysis Orchestrator Worker**
    ---
    Comprehensive intelligence analysis using pipeline orchestrator with multiple RSS feeds, conflict detection, and multi-source integration.
    
    **Topics**: Intelligence Analysis, Pipeline Orchestration, Multi-Source Integration, Conflict Resolution
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/intelligence/02_Intelligence_Analysis_Orchestrator_Worker.ipynb)

</div>

### Renewable Energy

<div class="grid cards" markdown>

-   :material-wind-turbine: **Energy Market Analysis**
    ---
    Analyzing trends and pricing in the renewable energy market using energy RSS feeds, EIA API, temporal knowledge graphs, TemporalPatternDetector, and seed data integration.
    
    **Topics**: Energy, Time Series, Temporal Analysis, Trend Prediction
    
    **Difficulty**: Intermediate
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/renewable_energy/01_Energy_Market_Analysis.ipynb)

</div>

### Supply Chain

<div class="grid cards" markdown>

-   :material-truck-delivery: **Supply Chain Data Integration**
    ---
    Integrating supply chain data to optimize logistics and reduce risk using logistics RSS feeds, deduplication, and multi-source relationship mapping.
    
    **Topics**: Logistics, Risk Management, Data Integration, Deduplication
    
    **Difficulty**: Advanced
    
    [Open Notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/supply_chain/01_Supply_Chain_Data_Integration.ipynb)

</div>

---

## How to Run

To run these notebooks locally:

1.  **Install Semantica from PyPI** (recommended):
    ```bash
    pip install semantica[all]
    pip install jupyter
    ```

2.  **Or install from source** (for development):
    ```bash
    git clone https://github.com/Hawksight-AI/semantica.git
    cd semantica
    pip install -e .[all]
    pip install jupyter
    ```

3.  **Launch Jupyter**:
    ```bash
    jupyter notebook
    ```

!!! tip "Using Docker"
    You can also run the cookbook using Docker:
    ```bash
    docker run -p 8888:8888 hawksight/semantica-cookbook
    ```
