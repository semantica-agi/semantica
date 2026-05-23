---
title: "Triplet Store Module"
description: "RDF triple storage with SPARQL queries and bulk loading — Blazegraph, Apache Jena, and RDF4J."
icon: "table"
---

`semantica.triplet_store` provides W3C-standard RDF storage with full SPARQL query support. Use it when you need semantic web compatibility, OWL reasoning, SPARQL-based queries, or standards-compliant RDF serialization.

## What You Get

- **`TripletStore`** — unified interface for all RDF backends
- **Backends** — Blazegraph, Apache Jena (Fuseki), RDF4J
- **SPARQL** — full SELECT, CONSTRUCT, ASK, and UPDATE query support
- **Bulk loading** — efficient batch import for large triple sets
- **Import / Export** — Turtle, JSON-LD, N-Triples, RDF/XML

## Basic Usage

```python
from semantica.triplet_store import TripletStore

store = TripletStore(
    backend="blazegraph",
    endpoint="http://localhost:9999/blazegraph/sparql"
)

# Add a single triplet
store.add_triplet(
    subject="http://example.org/apple_inc",
    predicate="http://example.org/founded_by",
    obj="http://example.org/steve_jobs"
)

# Bulk load a list of triplets
store.add_triplets_bulk(triplets)
```

## SPARQL Queries

```python
# SELECT — returns tabular results
results = store.sparql("""
    PREFIX ex: <http://example.org/>
    SELECT ?person ?company WHERE {
        ?person ex:founded ?company .
        ?company ex:located_in ex:SiliconValley .
    }
""")

for row in results:
    print(row["person"], row["company"])

# CONSTRUCT — returns a graph of matched triples
graph = store.sparql_construct("""
    PREFIX ex: <http://example.org/>
    CONSTRUCT {
        ?s ex:connected_to ?o
    } WHERE {
        ?s ex:founded ?company .
        ?company ex:has_investor ?o .
    }
""")

# ASK — returns True/False
exists = store.sparql_ask("""
    PREFIX ex: <http://example.org/>
    ASK { ex:apple_inc ex:founded_by ex:steve_jobs . }
""")

# UPDATE — insert or delete triples
store.sparql_update("""
    PREFIX ex: <http://example.org/>
    INSERT DATA {
        ex:apple_inc ex:listed_on ex:NASDAQ .
    }
""")
```

## Backends

```python
# Blazegraph — open source, SPARQL 1.1
store = TripletStore(
    backend="blazegraph",
    endpoint="http://localhost:9999/blazegraph/sparql",
    namespace="semantica"
)

# Apache Jena Fuseki — open source, widely used
store = TripletStore(
    backend="jena",
    endpoint="http://localhost:3030/dataset/sparql",
    update_endpoint="http://localhost:3030/dataset/update"
)

# RDF4J — enterprise-grade, Eclipse Foundation
store = TripletStore(
    backend="rdf4j",
    server_url="http://localhost:8080/rdf4j-server",
    repository_id="semantica"
)
```

## Backend Comparison

| Backend | License | Query Language | Best For |
| ------- | ------- | -------------- | -------- |
| Blazegraph | Open source | SPARQL 1.1 | Wikidata-style workloads |
| Apache Jena | Apache 2.0 | SPARQL 1.1 | General RDF, OWL reasoning |
| RDF4J | Eclipse 1.0 | SPARQL 1.1 | Enterprise, Java ecosystems |

## Import and Export

```python
# Import from file
store.import_file("ontology.ttl",  format="turtle")
store.import_file("data.jsonld",   format="json-ld")
store.import_file("triples.nt",    format="nt")

# Export to file
store.export("output.ttl", format="turtle")
store.export("output.nt",  format="nt")
store.export("output.xml", format="xml")
```

## Graph Management

```python
# Named graphs — store triples in isolated contexts
store.add_triplet(
    subject="http://example.org/a",
    predicate="http://example.org/p",
    obj="http://example.org/b",
    graph="http://example.org/graph1"
)

# Query a specific named graph
results = store.sparql("""
    SELECT ?s ?p ?o FROM <http://example.org/graph1> WHERE {
        ?s ?p ?o .
    }
""")

# List all named graphs
graphs = store.list_graphs()

# Clear a named graph
store.clear_graph("http://example.org/graph1")
```

## Integration with Export Module

The Export module can write RDF that the triplet store then imports:

```python
from semantica.export import RDFExporter
from semantica.triplet_store import TripletStore

# Export KG to Turtle
exporter = RDFExporter()
exporter.export_to_file(kg, "output.ttl", format="turtle")

# Load into triplet store
store = TripletStore(backend="jena", endpoint="http://localhost:3030/dataset/sparql")
store.import_file("output.ttl", format="turtle")

# Now query with SPARQL
results = store.sparql("SELECT * WHERE { ?s ?p ?o } LIMIT 10")
```

<CardGroup cols={2}>
  <Card title="Export" icon="file-export" href="export">
    Export knowledge graphs to RDF formats.
  </Card>
  <Card title="Ontology" icon="sitemap" href="ontology">
    Load OWL ontologies into a triplet store.
  </Card>
  <Card title="Reasoning" icon="microchip" href="reasoning">
    SPARQL-based property chain inference.
  </Card>
  <Card title="Graph Store" icon="server" href="graph_store">
    Property graph alternative for Cypher queries.
  </Card>
</CardGroup>
