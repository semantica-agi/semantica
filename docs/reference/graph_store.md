---
title: "Graph Store Module"
description: "Unified interface for Neo4j, FalkorDB, Apache AGE, and Amazon Neptune graph databases."
icon: "server"
---

`semantica.graph_store` provides a single API for persisting and querying knowledge graphs in production graph databases. Swap backends with a one-line change — no application code changes needed.

## What You Get

- **`GraphStore`** — unified interface across all backends
- **Backends** — Neo4j, FalkorDB, Apache AGE (PostgreSQL), Amazon Neptune, NetworkX (in-memory)
- **Cypher queries** — full Cypher support for Neo4j and FalkorDB
- **Bulk operations** — batched node and edge loading with configurable batch sizes
- **Schema management** — create indexes and uniqueness constraints
- **Path traversal** — find paths between nodes with hop limits and relationship type filters

## Basic Usage

```python
from semantica.graph_store import GraphStore

store = GraphStore(
    backend="neo4j",
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)

store.add_nodes(entities)
store.add_edges(relationships)

results = store.query("MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 10")
```

## Backends

<Tabs>
  <Tab title="Neo4j">

```python
store = GraphStore(
    backend="neo4j",
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
    database="neo4j"    # optional — targets default database
)
```

Best for: production workloads, complex Cypher queries, Bloom visualization.

  </Tab>
  <Tab title="FalkorDB">

```python
store = GraphStore(
    backend="falkordb",
    host="localhost",
    port=6379,
    graph_name="semantica"
)
```

Best for: ultra-low latency queries over Redis protocol, edge deployments.

  </Tab>
  <Tab title="Apache AGE">

```python
store = GraphStore(
    backend="apache_age",
    connection_string="postgresql://user:pass@localhost/graphdb",
    graph_name="semantica"
)
```

Best for: teams already running PostgreSQL who want graph queries without a separate service. See the [Apache AGE Guide](../graph_stores/apache_age) for setup.

  </Tab>
  <Tab title="Amazon Neptune">

```python
store = GraphStore(
    backend="neptune",
    endpoint="your-cluster.cluster-xxxx.us-east-1.neptune.amazonaws.com",
    port=8182,
    region="us-east-1"
)
```

Best for: managed AWS deployments needing both SPARQL and Gremlin support.

  </Tab>
  <Tab title="In-Memory">

```python
store = GraphStore(backend="networkx")
```

Best for: development, testing, and graphs that fit in RAM. Data is not persisted.

  </Tab>
</Tabs>

## Querying

```python
# Cypher query with parameters (Neo4j, FalkorDB)
results = store.query(
    "MATCH (p:Person)-[:WORKS_FOR]->(o:Organization) WHERE o.name = $org RETURN p",
    parameters={"org": "Apple Inc."}
)

# Path traversal between two nodes
paths = store.find_paths(
    start_node="steve_jobs",
    end_node="apple_inc",
    max_hops=3,
    relationship_types=["FOUNDED", "WORKED_AT"]
)
```

## Graph Operations

```python
# Add a single node
store.add_node(
    "apple_inc",
    node_type="Organization",
    properties={"founded": 1976, "hq": "Cupertino"}
)

# Add a directed relationship
store.add_edge(
    "steve_jobs", "apple_inc",
    "FOUNDED",
    properties={"year": 1976}
)

# Bulk operations — use for large datasets
store.add_nodes_bulk(entities,       batch_size=1000)
store.add_edges_bulk(relationships,  batch_size=1000)

# Delete
store.delete_node("node_id")
store.delete_edge("edge_id")

# Get neighbors
neighbors = store.get_neighbors(
    "apple_inc",
    relationship_type="HAS_EMPLOYEE",
    direction="in"    # "in" | "out" | "both"
)
```

## Schema Management

Create indexes and constraints to improve query performance:

```python
# Index for fast label lookups
store.create_index(label="Person", property="name")

# Uniqueness constraint
store.create_constraint(
    label="Organization",
    property="id",
    constraint_type="unique"
)

# Inspect current schema
schema = store.get_schema()
print(schema["labels"])
print(schema["indexes"])
print(schema["constraints"])
```

## Backend Comparison

| Backend | Query Language | Deployment | Best For |
| ------- | -------------- | ---------- | -------- |
| Neo4j | Cypher | Self-hosted / Aura | Production, complex traversals |
| FalkorDB | Cypher | Redis-based | Ultra-low latency, edge |
| Apache AGE | OpenCypher | PostgreSQL | Teams already on Postgres |
| Amazon Neptune | SPARQL / Gremlin | AWS managed | Cloud-native AWS deployments |
| NetworkX | Python API | In-memory | Development and testing |

<CardGroup cols={2}>
  <Card title="KG Module" icon="diagram-project" href="kg">
    Build the graph before persisting it.
  </Card>
  <Card title="Apache AGE Guide" icon="database" href="../graph_stores/apache_age">
    PostgreSQL-based graph storage setup.
  </Card>
  <Card title="Triplet Store" icon="table" href="triplet_store">
    RDF triple store for semantic web and SPARQL queries.
  </Card>
  <Card title="Visualization" icon="chart-bar" href="visualization">
    Visualize graphs stored in any backend.
  </Card>
</CardGroup>
