---
title: "Triplet Store Module"
description: "RDF triple storage with SPARQL queries and bulk loading — Blazegraph, Apache Jena, and RDF4J."
icon: "table"
---

`semantica.triplet_store` provides W3C-standard RDF storage with full SPARQL query support. Use it when you need semantic web compatibility, OWL reasoning, SPARQL-based queries, or standards-compliant RDF serialization.

## Exported Classes

| Class | Role |
| --- | --- |
| `TripletStore` | Unified interface: `add_triplet`, `get_triplets`, `delete_triplet`, `execute_query`, `bulk_load` |
| `QueryEngine` | SPARQL 1.1 execution with query optimization and result streaming |
| `BulkLoader` | High-volume RDF loading with progress tracking and transaction batching |
| `BlazegraphStore` | Blazegraph REST API — Named Graphs, SPARQL 1.1 Update, GeoSPARQL |
| `JenaStore` | Apache Jena Fuseki — TDB2 backend, GeoSPARQL, SPARQL 1.1 |
| `RDF4JStore` | Eclipse RDF4J — SailRepository, in-memory or native store |

## What You Get

<CardGroup cols={2}>
  <Card title="TripletStore" icon="server">
    Unified interface across Blazegraph, Apache Jena (Fuseki), and RDF4J — swap backends with one parameter.
  </Card>
  <Card title="TripletStore (in-memory)" icon="bolt">
    Zero-setup in-memory mode via `backend="memory"` for unit tests and small datasets — no server required.
  </Card>
  <Card title="SPARQL" icon="magnifying-glass">
    Full SELECT, CONSTRUCT, ASK, and UPDATE query support with pagination for large result sets.
  </Card>
  <Card title="OWL Reasoning" icon="microchip">
    Apache Jena supports OWL and RDFS inference natively — subclass and property chain queries automatically resolved.
  </Card>
  <Card title="Named Graphs" icon="diagram-project">
    Isolate triples by source, dataset, or time period using named graph management.
  </Card>
  <Card title="Import / Export" icon="file-export">
    Load and serialize to Turtle, JSON-LD, N-Triples, and RDF/XML with a single method call.
  </Card>
</CardGroup>

## Quick Start

<Steps>
  <Step title="Connect to a backend">
    ```python
    from semantica.triplet_store import TripletStore

    store = TripletStore(
        backend="blazegraph",
        endpoint="http://localhost:9999/blazegraph/sparql"
    )
    ```
  </Step>
  <Step title="Add triplets">
    ```python
    # Add a single triplet
    store.add_triplet(
        subject="http://example.org/apple_inc",
        predicate="http://example.org/founded_by",
        obj="http://example.org/steve_jobs"
    )

    # Bulk load a list of triplets
    store.add_triplets_bulk(triplets)
    ```
  </Step>
  <Step title="Query with SPARQL">
    ```python
    results = store.sparql("""
        PREFIX ex: <http://example.org/>
        SELECT ?person ?company WHERE {
            ?person ex:founded ?company .
            ?company ex:located_in ex:SiliconValley .
        }
    """)

    for row in results:
        print(row["person"], row["company"])
    ```
  </Step>
  <Step title="Export to file">
    ```python
    store.export("output.ttl", format="turtle")
    store.export("output.nt",  format="nt")
    store.export("output.xml", format="xml")
    ```
  </Step>
</Steps>

## Backends

<Tabs>
  <Tab title="Blazegraph">
    ```python
    from semantica.triplet_store import TripletStore

    store = TripletStore(
        backend="blazegraph",
        endpoint="http://localhost:9999/blazegraph/sparql",
        namespace="semantica"
    )
    ```

    Best for: Wikidata-style workloads, high triple counts, SPARQL 1.1 full support.
  </Tab>
  <Tab title="Apache Jena">
    ```python
    store = TripletStore(
        backend="jena",
        endpoint="http://localhost:3030/dataset/sparql",
        update_endpoint="http://localhost:3030/dataset/update"
    )
    ```

    Best for: General RDF, standard SPARQL, production deployments needing OWL inference.

    **Enable OWL reasoning:**

    ```python
    store = TripletStore(
        backend="jena",
        endpoint="http://localhost:3030/dataset/sparql",
        update_endpoint="http://localhost:3030/dataset/update",
        reasoner="OWL",        # "OWL" | "RDFS" | "OWL_MINI" | None
    )

    # Load an OWL ontology — subclass/property chain inferences are automatic
    store.import_file("ontology.ttl", format="turtle")
    store.add_triplets_bulk(data_triplets)

    # Query using inferred relationships
    results = store.sparql("""
        SELECT ?person WHERE {
            ?person a ex:Employee .       # inferred via subClassOf chain
        }
    """)
    ```
  </Tab>
  <Tab title="RDF4J">
    ```python
    store = TripletStore(
        backend="rdf4j",
        server_url="http://localhost:8080/rdf4j-server",
        repository_id="semantica"
    )
    ```

    Best for: Enterprise Java ecosystems, Eclipse Foundation deployments, plugin-based reasoning.
  </Tab>
  <Tab title="Backend Comparison">

    | Backend | License | OWL Reasoning | Hosted Option | Best For |
    | ------- | ------- | ------------- | ------------- | -------- |
    | Blazegraph | Open source | No | Self-hosted | Wikidata-style workloads, high triple count |
    | Apache Jena | Apache 2.0 | Yes (OWL/RDFS) | Self-hosted | General RDF, OWL reasoning, standard SPARQL |
    | RDF4J | Eclipse 1.0 | Via plugin | Self-hosted or cloud | Enterprise Java ecosystems |
    | InMemory | Built-in | No | N/A | Unit tests, small graphs, no server required |

  </Tab>
</Tabs>

## Namespace Prefix Management

Register custom prefixes to keep SPARQL queries readable:

```python
from semantica.triplet_store import TripletStore
from semantica.ontology import NamespaceManager

ns = NamespaceManager(base_uri="http://example.org/")
ns.register("ex",     "http://example.org/")
ns.register("schema", "https://schema.org/")
ns.register("owl",    "http://www.w3.org/2002/07/owl#")

store = TripletStore(backend="jena", endpoint="...")

# Registered prefixes are automatically prepended to every SPARQL query
results = store.sparql("""
    SELECT ?company WHERE {
        ?person ex:works_for ?company ;
                schema:name  "Alice" .
    }
""")
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

## SPARQL Result Pagination

For large result sets, paginate with LIMIT and OFFSET:

```python
page_size = 1000
offset    = 0

while True:
    results = store.sparql(f"""
        SELECT ?s ?p ?o WHERE {{
            ?s ?p ?o .
        }}
        ORDER BY ?s
        LIMIT {page_size} OFFSET {offset}
    """)
    if not results:
        break
    process_batch(results)
    offset += page_size
```

## Named Graph Management

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

## Tips and Common Pitfalls

<Tip>
  **Use Apache Jena (Fuseki) for development and Blazegraph for production.** Jena runs with a single Docker command, supports OWL reasoning natively, and requires no licence. Switch to Blazegraph for high-throughput workloads by changing the `backend=` parameter — no other code changes needed.
</Tip>

<Warning>
  **Paginate large SPARQL result sets.** A `SELECT * WHERE { ?s ?p ?o }` against a million-triple store can return gigabytes of data. Always include `LIMIT` and `OFFSET` in exploratory queries, and iterate with `page_size` when you need full coverage. Unbounded queries against large stores will OOM or timeout.
</Warning>

<Tip>
  **Use named graphs to isolate sources.** `store.add_triplet(..., graph="http://example.org/source_A")` puts triples into a named graph. You can then query just that source, merge selectively, or clear it without touching other data — far safer than mixing all triples into the default graph.
</Tip>

<Tip>
  **Register namespace prefixes before querying.** `NamespacePrefixManager` lets you write `?s ex:name ?o` instead of `?s <http://example.org/name> ?o`. Without prefixes, SPARQL queries against domain ontologies become unreadable and error-prone.
</Tip>

<Warning>
  **Enable OWL reasoning only when you need it.** `reasoner="OWL"` significantly increases query planning overhead. For simple triple lookups or SPARQL SELECT queries, leave reasoning off (`reasoner=None`) and enable it only for queries that depend on class hierarchies or property chains.
</Warning>

<Tip>
  **Export to Turtle before migrating backends.** If you need to move from Jena to Blazegraph (or any other store), `store.export("dump.ttl", format="turtle")` produces a portable file that any SPARQL store can import. Don't rely on backend-specific dump formats.
</Tip>

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
