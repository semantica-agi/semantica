---
title: "Architecture"
description: "Three-layer, modular architecture designed for independent component use, clean separation of concerns, and full extensibility."
icon: "building"
---

Semantica is built around a three-layer modular architecture. Import only what you need — the framework never forces a full stack. Every component is independently swappable, and every layer communicates through clean interfaces with no hidden coupling.

## Three-Layer Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Data Ingestion                                        │
│  Files · Web · APIs · Databases · Streams                       │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: Semantic Processing                                   │
│  Parse · Normalize · Extract · Build · QA                       │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: Application                                           │
│  GraphRAG · AI Agents · Analytics · Export · Visualization      │
└─────────────────────────────────────────────────────────────────┘
```

<Tabs>

<Tab title="Layer 1 — Ingestion">

Loads data from any source into the pipeline as a unified `SourceDocument`.

| Source | Module | Notes |
| ------ | ------ | ----- |
| PDF, DOCX, PPTX, HTML, JSON, CSV | `ingest.FileIngestor` | Supports archives, recursive directory scan |
| Parquet | `ingest.ParquetIngestor` | PyArrow, Hive-style partitions (v0.5.0) |
| XML | `ingest.XMLIngestor` | XXE-safe lxml, XSD/DTD validation (v0.5.0) |
| Web pages | `ingest.WebIngestor` | Configurable depth, link filtering |
| SQL / Snowflake | `ingest.DBIngestor` / `ingest.SnowflakeIngestor` | Custom SQL, schema introspection |
| Kafka / streams | `ingest.StreamIngestor` | Real-time feed ingestion |
| Email | `ingest.EmailIngestor` | IMAP/SMTP with attachment extraction |
| Repositories | `ingest.RepoIngestor` | Git repos, code structure |
| MCP | `ingest.MCPIngestor` | Model Context Protocol sources |

</Tab>

<Tab title="Layer 2 — Semantic Processing">

The core intelligence engine — transforms raw text into structured, queryable knowledge.

| Step | Module | What it does |
| ---- | ------ | ------------ |
| Parse | `parse.DocumentParser` / `parse.DoclingParser` | Text + layout extraction, table detection |
| Normalize | `normalize` | Canonical forms, date/name standardization, encoding fix |
| Extract | `semantic_extract` | NER, relation extraction, event detection, triplets |
| Build | `kg.GraphBuilder` | Entity merging, edge construction, graph assembly |
| Embed | `embeddings` | Sentence-Transformers, FastEmbed, OpenAI, BGE |
| QA | `deduplication`, `conflicts` | Duplicate detection, conflict resolution, validation |
| Temporal | `kg.TemporalKnowledgeGraph` | `valid_from` / `valid_until`, Allen interval algebra (v0.4.0) |

</Tab>

<Tab title="Layer 3 — Application">

Consumes the knowledge graph for downstream use cases.

| Use Case | Module | Description |
| -------- | ------ | ----------- |
| GraphRAG | `context.AgentContext` | Graph-grounded retrieval for LLMs |
| Agent memory | `context.ContextGraph` | Persistent semantic memory across agent runs |
| Decision tracking | `context.AgentContext` | Record, trace, and audit every agent decision |
| Ontology Hub | `explorer` | Visual editor, SHACL Studio, alignment UI (v0.5.0) |
| Multi-agent | `integrations.agno` | Shared context, team-level memory, KG toolkit |
| Visualization | `visualization` | Interactive HTML graphs, embedding plots, temporal views |
| Export | `export` | RDF, Parquet, ArangoDB AQL, OWL, CSV, Arrow |
| Reasoning | `reasoning` | Forward chaining, Rete, Datalog, SPARQL, abductive |

</Tab>

</Tabs>

## Data Flow

Every pipeline follows the same linear path from raw source to delivered output:

```text
Ingest      →  raw data from files, web, databases, streams
Parse       →  structured text and layout extraction
Normalize   →  canonical forms, date and name standardization
Extract     →  entities, relationships, events, triplets
Build       →  entity resolution and graph construction
QA          →  deduplication, conflict resolution, validation
Store       →  vector store, graph store, triplet store
Deliver     →  GraphRAG, agents, export, visualization
```

## Module Map

| Layer | Modules |
| ----- | ------- |
| Ingestion | `ingest`, `parse`, `split`, `normalize` |
| Semantic | `semantic_extract`, `kg`, `ontology`, `reasoning` |
| Storage | `embeddings`, `vector_store`, `graph_store`, `triplet_store` |
| Quality | `deduplication`, `conflicts` |
| Context | `context`, `provenance`, `change_management` |
| Output | `export`, `visualization`, `pipeline`, `explorer` |
| Utilities | `llms`, `mcp_server`, `seed`, `evals`, `core`, `utils` |

## Extension Points

Every layer exposes a registry-based extension point. Register custom implementations and they participate in the full pipeline with zero changes to core code.

<CodeGroup>

```python Custom Ingestor
from semantica.ingest.registry import method_registry

def custom_file_ingestor(source):
    # Return a list of document dicts with 'text', 'metadata', 'source'
    return [{"text": "...", "metadata": {}, "source": source}]

# Register under the "file" task category with a unique name
method_registry.register("file", "my_custom_format", custom_file_ingestor)

available = method_registry.list_all("file")
```

```python Custom Extractor
from semantica.semantic_extract.registry import method_registry

def custom_entity_extractor(text, config=None):
    # Return a list of entity dicts with 'text', 'type', 'confidence'
    return [{"text": "...", "type": "CUSTOM_TYPE", "confidence": 0.9}]

# Register under the "entity" extraction task
method_registry.register("entity", "my_extractor", custom_entity_extractor)
```

```python Custom Plugin
from semantica.core import PluginRegistry

class MyPlugin:
    def process(self, graph, config):
        # Modify the graph in place and return it
        return graph

registry = PluginRegistry()
registry.register_plugin("my_plugin", MyPlugin, version="1.0.0")
```

</CodeGroup>

## Design Decisions

<AccordionGroup>

<Accordion title="Modularity — use only what you need" icon="puzzle-piece">

Every component works standalone. `NERExtractor` runs without a graph store. `VectorStore` runs without decision tracking. The framework never forces a full stack instantiation — you pay only for what you import.

</Accordion>

<Accordion title="Pluggability — extend without modifying core" icon="plug">

Custom ingestors, extractors, validators, and exporters follow the same base class pattern. Register them via `PluginRegistry` and they participate in the full pipeline — provenance tracking, retry policies, and parallel execution included — with no changes to core code.

</Accordion>

<Accordion title="Provenance by default" icon="link">

Lineage tracking is built into graph construction at the lowest level. Every node and edge carries a `source_id` pointing back to the originating document, extraction method, and timestamp. There's no opt-in required — provenance is always on.

</Accordion>

<Accordion title="Configuration over convention" icon="sliders">

Centralized `ConfigManager` with environment variable overrides. No magic defaults — all behavior is explicit and overridable. Suitable for multi-environment deployments where dev, staging, and production need different backends.

</Accordion>

</AccordionGroup>

## Performance Characteristics

| Characteristic | Mechanism |
| -------------- | --------- |
| **Parallel execution** | `Pipeline(workers=N)` with configurable workers per stage |
| **Delta processing** | Incremental graph updates — no full recompute on new data |
| **Streaming ingestion** | Process large corpora without loading everything into memory |
| **Backend flexibility** | Swap in-memory NetworkX for Neo4j / FalkorDB with no API changes |
| **Deduplication v2** | `blocking_v2`, `hybrid_v2`, `semantic_v2` — up to 7x faster than v1 |
| **Indexed search** | Explorer search at 0.004ms on 118k nodes (v0.5.0) |

<CardGroup cols={2}>
  <Card title="Modules" icon="cubes" href="modules">
    Full module documentation with code examples.
  </Card>
  <Card title="Learning More" icon="graduation-cap" href="learning-more">
    Configuration reference, performance guide, and troubleshooting.
  </Card>
  <Card title="Pipeline Reference" icon="gear" href="reference/pipeline">
    Pipeline orchestration, workers, and retry policies.
  </Card>
  <Card title="Core Reference" icon="network-wired" href="reference/core">
    Framework lifecycle, plugin registry, and configuration.
  </Card>
</CardGroup>
