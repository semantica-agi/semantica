---
title: "Export Module"
description: "Export knowledge graphs to RDF, Parquet, LPG, ArangoDB AQL, CSV, GraphML, OWL, JSON-LD, and vector formats."
icon: "file-export"
---

`semantica.export` serializes knowledge graphs to every downstream format — semantic web standards, analytics pipelines, graph databases, and vector stores. All exporters share a consistent `export(graph, path, format)` interface.

## Exported Classes

```python
from semantica.export import (
    RDFExporter,         # Turtle, JSON-LD, N-Triples, RDF/XML
    ParquetExporter,     # columnar Parquet (Spark, BigQuery, Databricks, Snowflake)
    LPGExporter,         # Cypher CREATE/MERGE for Neo4j / Memgraph
    ArangoAQLExporter,   # AQL INSERT for ArangoDB
    GraphExporter,       # GraphML, GEXF, Graphviz DOT
    OWLExporter,         # OWL 2.0 in Turtle, XML, JSON-LD
    CSVExporter,         # flat CSV nodes + edges
    VectorExporter,      # embedding vectors as JSON, NumPy, or FAISS
    ArrowExporter,       # Apache Arrow IPC (zero-copy transfer)
    DistanceExporter,    # semantic distance matrices and ego-graphs
    ReportGenerator,     # human-readable analytics reports (HTML, Markdown, JSON)
    NamespaceManager,    # register and resolve RDF namespace prefixes
    SemanticNetworkYAMLExporter,  # YAML semantic network export
    # Convenience functions
    export_rdf, export_parquet, export_csv, export_lpg,
    export_arango, export_graph, export_owl, export_vector,
    export_arrow, generate_report,
)
```

## What You Get

<CardGroup cols={2}>
  <Card title="RDFExporter" icon="diagram-project">
    Turtle, JSON-LD, N-Triples, RDF/XML with namespace management and optional PROV-O provenance embedding.
  </Card>
  <Card title="ParquetExporter" icon="layer-group">
    Columnar storage for Spark, BigQuery, Databricks, and Snowflake with explicit PyArrow typing.
  </Card>
  <Card title="LPG & ArangoDB" icon="server">
    Cypher CREATE/MERGE for Neo4j and Memgraph; AQL INSERT for ArangoDB vertex and edge collections.
  </Card>
  <Card title="Graph Formats" icon="chart-bar">
    GraphML, GEXF, DOT for Gephi and Graphviz. OWL 2.0 ontology export in Turtle, XML, and JSON-LD.
  </Card>
  <Card title="Vector & Arrow" icon="vector-square">
    JSON, NumPy `.npy`, and FAISS index export for embedding vectors. Apache Arrow IPC for zero-copy transfer.
  </Card>
  <Card title="Distance & Reports" icon="chart-line">
    Distance matrix CSV/JSON from Distance Intelligence (v0.5.0). HTML, Markdown, and JSON analytics reports.
  </Card>
</CardGroup>

## Quick Start

<Steps>
  <Step title="Choose your format and instantiate an exporter">
    ```python
    from semantica.export import RDFExporter

    exporter = RDFExporter()
    ```
  </Step>
  <Step title="Export the graph">
    ```python
    # Export to RDF string, then write to file
    rdf_str = exporter.export_to_rdf(graph, format="turtle")
    with open("output.ttl", "w") as f:
        f.write(rdf_str)
    ```
  </Step>
  <Step title="Use convenience functions for one-liners">
    ```python
    from semantica.export import export_rdf, export_parquet, export_csv

    export_rdf(graph,     "output.ttl",   format="turtle")
    export_parquet(graph, "output/",      compression="snappy")
    export_csv(graph,     "nodes.csv",    target="nodes")
    ```
  </Step>
  <Step title="Stream large graphs to avoid OOM">
    ```python
    from semantica.export import ParquetExporter

    exporter = ParquetExporter(compression="snappy")
    exporter.export_stream(graph, output_dir="output/", batch_size=10_000)
    ```
  </Step>
</Steps>

## Exporters

<Tabs>
  <Tab title="RDF">
    Export to W3C RDF formats — Turtle, JSON-LD, N-Triples, and RDF/XML:

    ```python
    from semantica.export import RDFExporter

    exporter = RDFExporter()

    # Export to RDF string — write to file manually
    rdf_str = exporter.export_to_rdf(graph, format="turtle")   # Turtle (most readable)
    rdf_str = exporter.export_to_rdf(graph, format="json-ld")  # JSON-LD (APIs, Linked Data)
    rdf_str = exporter.export_to_rdf(graph, format="nt")       # N-Triples (streaming-friendly)
    rdf_str = exporter.export_to_rdf(graph, format="xml")      # RDF/XML (W3C standard)

    with open("output.ttl", "w") as f:
        f.write(exporter.export_to_rdf(graph, format="turtle"))
    ```

    **Custom namespace management:**

    ```python
    from semantica.export import NamespaceManager, RDFExporter

    ns_manager = NamespaceManager()
    ns_manager.register("ex",     "http://example.org/")
    ns_manager.register("schema", "https://schema.org/")

    exporter = RDFExporter(namespace_manager=ns_manager)
    ```

    **Export with PROV-O provenance:**

    ```python
    from semantica.export import RDFExporter
    from semantica.provenance import ProvenanceManager

    provenance = ProvenanceManager()
    # ... track entities during extraction ...

    exporter = RDFExporter(include_provenance=True, provenance_manager=provenance)
    exporter.export_to_file(graph, "output_with_prov.ttl", format="turtle")
    # → Each entity's prov:wasGeneratedBy, prov:wasDerivedFrom, prov:hadPrimarySource
    #   triples are included alongside the entity data triples
    ```
  </Tab>
  <Tab title="Columnar & Analytics">
    Columnar formats for analytics pipelines and human-readable export:

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

    ```python
    from semantica.export import CSVExporter

    exporter = CSVExporter(delimiter=",")
    exporter.export_nodes(graph, "nodes.csv")
    exporter.export_edges(graph, "edges.csv")
    ```

    ```python
    from semantica.export import SemanticNetworkYAMLExporter

    exporter = SemanticNetworkYAMLExporter()
    exporter.export(graph, "graph.yaml")

    yaml_str = exporter.to_string(graph)
    ```
  </Tab>
  <Tab title="Graph DB Import">
    Export Cypher or AQL statements for direct graph database import:

    ```python
    from semantica.export import LPGExporter

    exporter = LPGExporter()

    # CREATE statements
    cypher = exporter.to_cypher(graph)
    exporter.export(graph, "import.cypher", format="cypher")

    # MERGE statements (idempotent — safe to re-run)
    cypher_merge = exporter.to_cypher(graph, use_merge=True)
    ```

    ```python
    from semantica.export import ArangoAQLExporter

    exporter = ArangoAQLExporter(
        vertex_collection="entities",
        edge_collection="relationships"
    )

    aql = exporter.export(graph)                # returns AQL string
    exporter.export_to_file(graph, "import.aql")
    ```
  </Tab>
  <Tab title="Visualization">
    Export for graph visualization tools and OWL ontology distribution:

    ```python
    from semantica.export import GraphExporter

    exporter = GraphExporter()

    exporter.export(graph, "graph.graphml", format="graphml")  # Gephi, yEd
    exporter.export(graph, "graph.gexf",    format="gexf")     # Gephi streaming
    exporter.export(graph, "graph.dot",     format="dot")      # Graphviz
    ```

    ```python
    from semantica.export import OWLExporter

    exporter = OWLExporter()
    exporter.export(ontology, path="ontology.ttl",  format="turtle")
    exporter.export(ontology, path="ontology.owl",  format="xml")
    exporter.export(ontology, path="ontology.json", format="json-ld")
    ```
  </Tab>
  <Tab title="Specialized">
    Vector embeddings, Arrow IPC, distance matrices, and analytics reports:

    ```python
    from semantica.export import VectorExporter

    exporter = VectorExporter()
    exporter.export(embeddings, metadata, "vectors.json",  format="json")
    exporter.export(embeddings, metadata, "vectors.npy",   format="numpy")
    exporter.export(embeddings, metadata, "vectors.faiss", format="faiss")
    ```

    ```python
    from semantica.export import ArrowExporter

    exporter = ArrowExporter()
    exporter.export(graph, "graph.arrow")   # requires pyarrow
    ```

    ```python
    from semantica.export import DistanceExporter

    exporter = DistanceExporter()
    exporter.export_matrix(distance_matrix, node_labels, "distances.csv")
    exporter.export_ego(ego_neighborhood, center_node="Apple Inc.", path="ego.json")
    ```

    ```python
    from semantica.export import ReportGenerator

    generator = ReportGenerator()
    generator.generate(graph, analytics_result, "report.html",  format="html")
    generator.generate(graph, analytics_result, "report.md",    format="markdown")
    generator.generate(graph, analytics_result, "report.json",  format="json")
    ```
  </Tab>
</Tabs>

## Streaming Export

For graphs too large to hold in memory, use streaming export — writes incrementally without buffering the full graph:

```python
from semantica.export import RDFExporter, ParquetExporter

# Stream RDF — yields triples one at a time, no full-graph buffer
exporter = RDFExporter()
with exporter.stream(graph, format="turtle") as stream:
    for triple_line in stream:
        output_file.write(triple_line)

# Stream Parquet — writes row groups incrementally
exporter = ParquetExporter(compression="snappy")
exporter.export_stream(graph, output_dir="output/", batch_size=10_000)
```

Streaming is recommended for graphs with > 500k nodes.

## Selective Export

```python
# Export a subgraph
subgraph = graph.subgraph(node_ids=["apple_inc", "steve_jobs"])
export_rdf(subgraph, "subgraph.ttl", format="turtle")

# Export nodes by type
org_nodes = graph.filter(node_type="Organization")
export_parquet(org_nodes, "organizations.parquet")
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

## Format Reference

| Format | Exporter | Output | Best For |
| ------ | -------- | ------ | -------- |
| `turtle` | `RDFExporter` | `.ttl` | Readable RDF, ontology sharing |
| `json-ld` | `RDFExporter` | `.jsonld` | APIs, Linked Data, JSON pipelines |
| `nt` | `RDFExporter` | `.nt` | Streaming RDF, line-by-line processing |
| `xml` | `RDFExporter` | `.xml` | W3C RDF/XML, broadest compatibility |
| `parquet` | `ParquetExporter` | `.parquet` | Spark, BigQuery, Databricks, Snowflake |
| `cypher` | `LPGExporter` | `.cypher` | Neo4j, Memgraph import |
| `aql` | `ArangoAQLExporter` | `.aql` | ArangoDB vertex + edge collections |
| `graphml` | `GraphExporter` | `.graphml` | Gephi, yEd visualization |
| `gexf` | `GraphExporter` | `.gexf` | Gephi streaming format |
| `dot` | `GraphExporter` | `.dot` | Graphviz rendering |
| `owl` | `OWLExporter` | `.owl` / `.ttl` | OWL 2.0 ontology distribution |
| `csv` | `CSVExporter` | `.csv` | Spreadsheets, simple pipelines |
| `yaml` | `SemanticNetworkYAMLExporter` | `.yaml` | Human-readable, config-driven use |
| `arrow` | `ArrowExporter` | `.arrow` | Zero-copy inter-process transfer |
| `numpy` | `VectorExporter` | `.npy` | NumPy arrays from embeddings |
| `faiss` | `VectorExporter` | `.faiss` | Direct FAISS index files |
| `distance-matrix` | `DistanceExporter` | `.csv` / `.json` | Distance Intelligence matrices |
| `html` | `ReportGenerator` | `.html` | Human-readable analytics reports |
| `markdown` | `ReportGenerator` | `.md` | Documentation, GitHub |

## Tips and Common Pitfalls

<Tip>
  **Use `turtle` for human readability, `nt` for streaming.** Turtle is compact and readable for debugging and sharing ontologies. N-Triples (`.nt`) is line-oriented — one triple per line — making it safe to stream, concatenate, and process with standard Unix tools without loading the full file.
</Tip>

<Tip>
  **Use `ParquetExporter` for downstream analytics.** Parquet preserves column types (int, float, datetime) that CSV loses and is natively supported by Spark, BigQuery, Databricks, and Snowflake. Use `compression="snappy"` for a good balance of speed and compression ratio.
</Tip>

<Warning>
  **Stream large graphs with `export_stream()`.** For graphs with more than 500k nodes, use `exporter.export_stream(graph, ...)` instead of building the full RDF string in memory. Streaming writes incrementally — without it, a million-node export will likely OOM.
</Warning>

<Tip>
  **Include provenance for compliance exports.** For HIPAA, SOX, or FDA 21 CFR Part 11 exports, pass `include_provenance=True` to `RDFExporter`. This embeds W3C PROV-O lineage triples inline — auditors can verify every fact's source from a single file rather than cross-referencing separate systems.
</Tip>

<Tip>
  **Use selective export to reduce file size.** `graph.subgraph(node_ids=[...])` and `graph.filter(node_type="Organization")` let you export only the relevant subset. Full graph exports for compliance reports include noise; scoped exports are faster to produce, review, and transfer.
</Tip>

<Warning>
  **Match your export format to your consumer.** Neo4j → `cypher`; ArangoDB → `aql`; Gephi/yEd → `graphml` or `gexf`; semantic web tools → `turtle` or `json-ld`; analytics pipelines → `parquet`; zero-copy IPC → `arrow`. Using the wrong format forces the consumer to convert it, adding latency and potential data loss.
</Warning>

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
