---
title: "Export Module"
description: "Export knowledge graphs to RDF, Parquet, LPG, ArangoDB AQL, CSV, GraphML, OWL, JSON-LD, and vector formats."
icon: "file-export"
---

`semantica.export` serializes knowledge graphs to every downstream format — semantic web standards, analytics pipelines, graph databases, and vector stores. All exporters share a consistent `export(graph, path, format)` interface.

## What You Get

- **`RDFExporter`** — Turtle, JSON-LD, N-Triples, RDF/XML with namespace management
- **`ParquetExporter`** — columnar storage for Spark, BigQuery, Databricks, Snowflake
- **`LPGExporter`** — Cypher CREATE/MERGE statements for Neo4j and Memgraph
- **`ArangoAQLExporter`** — AQL INSERT statements for ArangoDB multi-model graphs
- **`GraphExporter`** — GraphML, GEXF, DOT for visualization tools like Gephi
- **`OWLExporter`** — OWL 2.0 ontology export in Turtle, XML, and JSON-LD
- **`CSVExporter`**, **`VectorExporter`**, **`ArrowExporter`**, **`DistanceExporter`**, **`ReportGenerator`**

## RDFExporter

```python
from semantica.export import RDFExporter

exporter = RDFExporter()

# Turtle (most readable RDF format)
exporter.export_to_file(graph, "output.ttl",    format="turtle")

# JSON-LD (best for APIs and Linked Data)
exporter.export_to_file(graph, "output.jsonld", format="json-ld")

# N-Triples (streaming-friendly, one triple per line)
exporter.export_to_file(graph, "output.nt",     format="nt")

# RDF/XML (W3C standard, broadest compatibility)
exporter.export_to_file(graph, "output.xml",    format="xml")

# Export to string instead of file
rdf_str = exporter.export_to_rdf(graph, format="turtle")
```

Custom namespace management:

```python
from semantica.export import NamespaceManager, RDFExporter

ns_manager = NamespaceManager()
ns_manager.register("ex",     "http://example.org/")
ns_manager.register("schema", "https://schema.org/")

exporter = RDFExporter(namespace_manager=ns_manager)
```

## ParquetExporter

Columnar export for Spark, BigQuery, Databricks, and Snowflake analytics pipelines:

```python
from semantica.export import ParquetExporter

exporter = ParquetExporter(compression="snappy")
# compression options: snappy | gzip | brotli | zstd | lz4

# Export nodes and edges as separate Parquet files
exporter.export_nodes(graph, "nodes.parquet")
exporter.export_edges(graph, "edges.parquet")

# Export full graph partitioned by node type
exporter.export(graph, output_dir="graph_parquet/", partition_by="node_type")
```

Schema is explicitly typed with PyArrow for clean Spark/BigQuery ingestion.

## LPGExporter

Labeled Property Graph export — Cypher statements for Neo4j and Memgraph:

```python
from semantica.export import LPGExporter

exporter = LPGExporter()

# CREATE statements
cypher = exporter.to_cypher(graph)
exporter.export(graph, "import.cypher", format="cypher")

# MERGE statements (idempotent — safe to re-run)
cypher_merge = exporter.to_cypher(graph, use_merge=True)
```

## ArangoAQLExporter

AQL INSERT statements for ArangoDB vertex and edge collections:

```python
from semantica.export import ArangoAQLExporter

exporter = ArangoAQLExporter(
    vertex_collection="entities",
    edge_collection="relationships"
)

aql = exporter.export(graph)                # returns AQL string
exporter.export_to_file(graph, "import.aql")
```

## GraphExporter

Export for visualization tools — GraphML, GEXF, and Graphviz DOT:

```python
from semantica.export import GraphExporter

exporter = GraphExporter()

exporter.export(graph, "graph.graphml", format="graphml")  # Gephi, yEd
exporter.export(graph, "graph.gexf",    format="gexf")     # Gephi streaming
exporter.export(graph, "graph.dot",     format="dot")      # Graphviz
```

## OWLExporter

OWL 2.0 ontology export in three serialization formats:

```python
from semantica.export import OWLExporter

exporter = OWLExporter()
exporter.export(ontology, path="ontology.ttl",  format="turtle")
exporter.export(ontology, path="ontology.owl",  format="xml")
exporter.export(ontology, path="ontology.json", format="json-ld")
```

## CSVExporter

Flat CSV export for spreadsheets and simple data pipelines:

```python
from semantica.export import CSVExporter

exporter = CSVExporter(delimiter=",")
exporter.export_nodes(graph, "nodes.csv")
exporter.export_edges(graph, "edges.csv")
```

## VectorExporter

Export embedding vectors for use in external vector stores:

```python
from semantica.export import VectorExporter

exporter = VectorExporter()
exporter.export(embeddings, metadata, "vectors.json",  format="json")
exporter.export(embeddings, metadata, "vectors.npy",   format="numpy")
exporter.export(embeddings, metadata, "vectors.faiss", format="faiss")
```

## ArrowExporter

Apache Arrow IPC format for zero-copy inter-process transfer:

```python
from semantica.export import ArrowExporter

exporter = ArrowExporter()
exporter.export(graph, "graph.arrow")
```

Requires `pyarrow`. Falls back gracefully if not installed.

## DistanceExporter

Export semantic distance matrices produced by Distance Intelligence (v0.5.0):

```python
from semantica.export import DistanceExporter

exporter = DistanceExporter()
exporter.export_matrix(distance_matrix, node_labels, "distances.csv")
exporter.export_ego(ego_neighborhood, center_node="Apple Inc.", path="ego.json")
```

## ReportGenerator

Generate human-readable analytics reports from graph metrics:

```python
from semantica.export import ReportGenerator

generator = ReportGenerator()

generator.generate(graph, analytics_result, "report.html",     format="html")
generator.generate(graph, analytics_result, "report.md",       format="markdown")
generator.generate(graph, analytics_result, "report.json",     format="json")
```

## Convenience Functions

```python
from semantica.export import (
    export_rdf, export_parquet, export_csv, export_lpg,
    export_arango, export_graph, export_owl, export_vector,
    export_arrow, generate_report
)

export_rdf(graph,     "output.ttl",    format="turtle")
export_parquet(graph, "output/",       compression="snappy")
export_csv(graph,     "nodes.csv",     target="nodes")
export_lpg(graph,     "import.cypher", method="cypher")
export_arango(graph,  "import.aql")
export_graph(graph,   "graph.graphml", format="graphml")
```

## Selective Export

```python
# Export a subgraph
subgraph = graph.subgraph(node_ids=["apple_inc", "steve_jobs"])
export_rdf(subgraph, "subgraph.ttl", format="turtle")

# Export nodes by type
org_nodes = graph.filter(node_type="Organization")
export_parquet(org_nodes, "organizations.parquet")
```

<CardGroup cols={2}>
  <Card title="Triplet Store" icon="table" href="triplet_store">
    Store RDF exports in a SPARQL-queryable backend.
  </Card>
  <Card title="Ontology" icon="sitemap" href="ontology">
    Export OWL ontologies.
  </Card>
  <Card title="Provenance" icon="link" href="provenance">
    Include provenance metadata in RDF exports.
  </Card>
  <Card title="Pipeline" icon="gear" href="pipeline">
    Add export as a final pipeline step.
  </Card>
</CardGroup>
