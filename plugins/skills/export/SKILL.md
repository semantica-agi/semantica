---
name: export
description: Export Semantica graphs, results, and provenance to JSON, RDF, Parquet, CSV, GraphML, and other formats.
---

# /semantica:export

Export knowledge graph data. Usage: `/semantica:export <format> [args]`

`$ARGUMENTS` = format + optional target or destination.

---

## `json [--output <path>] [--filter <query>]`

Export graph data as JSON.

```python
from semantica.export.methods import export_json

export_json(data=graph_data, file_path=output, format='json')
```

Output: JSON file or inline JSON payload.

---

## `rdf [--format turtle|rdfxml|jsonld|ntriples|n3] [--output <path>]`

Export the graph in RDF serialization.

```python
from semantica.export.methods import export_rdf

export_rdf(data=graph_data, file_path=output, format='turtle')
```

Return: RDF text or file path.

---

## `parquet [--output <path>]`

Export nodes and edges to Parquet for analytics.

```python
from semantica.export.methods import export_parquet

export_parquet(data=graph_data, file_path=output, compression='snappy')
```

Output: Parquet dataset ready for downstream processing.

---

## `graphml|gexf|dot [--output <path>]`

Export the graph to a supported graph format.

```python
from semantica.export import GraphExporter

exporter = GraphExporter(format='graphml', include_attributes=True)
exporter.export(graph_data, output)
```

Output: Graph format file suitable for visualization tools.
