---
title: "Graph Store Module"
description: "Unified interface for Neo4j, FalkorDB, Apache AGE, and Amazon Neptune graph databases."
icon: "server"
---

`semantica.graph_store` provides a single API for persisting and querying knowledge graphs in production graph databases. Swap backends with a one-line change — no application code changes needed.

## Exported Classes

```python
from semantica.graph_store import (
    # Core interface
    GraphStore,           # unified interface: add_node, add_edge, query, find_paths
    GraphManager,         # store management and operations
    NodeManager,          # node CRUD operations
    RelationshipManager,  # relationship CRUD operations
    QueryEngine,          # Cypher query execution with caching
    GraphAnalytics,       # centrality, community detection, shortest path
    # Backend stores
    Neo4jStore,           # Neo4j via Bolt — production workloads
    ApacheAgeStore,       # PostgreSQL + AGE extension
    AmazonNeptuneStore,   # AWS Neptune — SPARQL/Gremlin/openCypher
    FalkorDBStore,        # Redis-based — ultra-low latency
    # Convenience functions
    create_node,          # create_node(labels, properties)
    create_nodes,         # bulk: create_nodes(entities)
    create_relationship,  # create_relationship(start_id, end_id, rel_type)
    create_relationships, # bulk: create_relationships(rels)
    get_nodes,            # get_nodes(labels, filters)
    get_relationships,    # get_relationships(start_id, rel_type)
    get_neighbors,        # get_neighbors(node_id, direction="both")
    update_node,          # update_node(node_id, properties)
    delete_node,          # delete_node(node_id)
    execute_query,        # execute_query(cypher, parameters)
    shortest_path,        # shortest_path(source, target)
    run_analytics,        # run_analytics(graph, algorithm)
)
```

## What You Get

<CardGroup cols={2}>
  <Card title="GraphStore" icon="server">
    Unified interface across Neo4j, FalkorDB, Apache AGE, Amazon Neptune, and NetworkX.
  </Card>
  <Card title="QueryEngine" icon="magnifying-glass">
    Parameterized Cypher construction, query optimization, and result caching.
  </Card>
  <Card title="GraphAnalytics" icon="chart-line">
    Centrality, community detection, and path algorithms running directly against the backend.
  </Card>
  <Card title="Bulk Operations" icon="layer-group">
    Batched node and edge loading with configurable batch sizes — 10–100× faster than individual writes.
  </Card>
  <Card title="Schema Management" icon="table">
    Create indexes and uniqueness constraints to optimize query performance.
  </Card>
  <Card title="Path Traversal" icon="route">
    Find paths between nodes with hop limits and relationship type filters.
  </Card>
</CardGroup>

## Quick Start

<Steps>
  <Step title="Connect to a graph database">
    ```python
    from semantica.graph_store import GraphStore

    store = GraphStore(
        backend="neo4j",
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password",
    )
    ```
  </Step>
  <Step title="Create indexes before loading data">
    ```python
    store.create_index(label="Person",       property="name")
    store.create_index(label="Organization", property="name")
    ```
  </Step>
  <Step title="Load nodes and edges">
    ```python
    store.create_nodes(entities)
    store.add_edges(relationships)
    ```
  </Step>
  <Step title="Query the graph">
    ```python
    results = store.query(
        "MATCH (p:Person)-[:WORKS_FOR]->(o:Organization) WHERE o.name = $org RETURN p",
        parameters={"org": "Apple Inc."},
    )
    ```
  </Step>
</Steps>

## Backends

<Tabs>
  <Tab title="Neo4j (recommended)">
    ```python
    from semantica.graph_store import GraphStore

    store = GraphStore(
        backend="neo4j",
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password",
        database="neo4j",    # optional — targets default database
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
        graph_name="semantica",
    )
    ```

    Best for: ultra-low latency queries over Redis protocol, edge deployments.
  </Tab>
  <Tab title="Apache AGE">
    ```python
    store = GraphStore(
        backend="apache_age",
        connection_string="postgresql://user:pass@localhost/graphdb",
        graph_name="semantica",
    )
    ```

    Best for: teams already running PostgreSQL who want graph queries without a separate service. See the [Apache AGE Guide](../graph_stores/apache_age) for setup.
  </Tab>
  <Tab title="Amazon Neptune">
    ```python
    from semantica.graph_store import GraphStore

    # IAM authentication (recommended for production)
    store = GraphStore(
        backend="neptune",
        endpoint="your-cluster.cluster-xxxx.us-east-1.neptune.amazonaws.com",
        port=8182,
        region="us-east-1",
        use_iam_auth=True,    # uses boto3 default credential chain
    )

    # Gremlin traversal
    results = store.query("g.V().hasLabel('Person').limit(10)")

    # openCypher query
    results = store.query(
        "MATCH (p:Person)-[:WORKS_FOR]->(o:Organization) RETURN p, o",
        query_language="opencypher",
    )
    ```

    Best for: managed AWS deployments needing both SPARQL and Gremlin support.
  </Tab>
  <Tab title="NetworkX (in-memory)">
    ```python
    store = GraphStore(backend="networkx")
    ```

    Best for: development, testing, and graphs that fit in RAM. Data is not persisted.
  </Tab>
  <Tab title="Backend Comparison">

    | Backend | Query Language | Deployment | IAM Auth | Best For |
    | ------- | -------------- | ---------- | -------- | -------- |
    | Neo4j | Cypher | Self-hosted / Aura | No | Production, complex traversals, Bloom UI |
    | FalkorDB | Cypher | Redis-based | No | Ultra-low latency, edge deployments |
    | Apache AGE | OpenCypher | PostgreSQL extension | No | Teams already on Postgres |
    | Amazon Neptune | SPARQL / Gremlin / openCypher | AWS managed | Yes | Cloud-native, multi-model, compliance |
    | NetworkX | Python API | In-memory | No | Development, unit testing |

  </Tab>
</Tabs>

## Graph Operations

```python
# Add a single node
store.add_node(
    "apple_inc",
    node_type="Organization",
    properties={"founded": 1976, "hq": "Cupertino"},
)

# Add a directed relationship
store.add_edge(
    "steve_jobs", "apple_inc",
    "FOUNDED",
    properties={"year": 1976},
)

# Bulk operations — use for large datasets
store.create_nodes(entities)
store.add_edges(relationships)

# Delete
store.delete_node("node_id")
store.delete_edge("edge_id")

# Get neighbors
neighbors = store.get_neighbors(
    "apple_inc",
    relationship_type="HAS_EMPLOYEE",
    direction="in",    # "in" | "out" | "both"
)

# Path traversal between two nodes
paths = store.find_paths(
    start_node="steve_jobs",
    end_node="apple_inc",
    max_hops=3,
    relationship_types=["FOUNDED", "WORKED_AT"],
)
```

## QueryEngine

`QueryEngine` handles query construction, optimization, and caching:

```python
from semantica.graph_store import QueryEngine, GraphStore

store  = GraphStore(backend="neo4j", uri="bolt://localhost:7687", user="neo4j", password="password")
engine = QueryEngine(store, cache_ttl=300)   # cache results for 5 minutes

# Build parameterized Cypher
query, params = engine.build_query(
    node_labels=["Person"],
    filters={"department": "Engineering"},
    return_fields=["name", "email"],
    limit=50,
)
results = engine.execute(query, params)

# Explain query plan (Neo4j)
plan = engine.explain(query, params)
print(plan["profile"])

# Flush query cache
engine.clear_cache()
```

## GraphAnalytics

Built-in graph analytics that run directly against the stored backend — no data export required:

```python
from semantica.graph_store import GraphAnalytics, GraphStore

store     = GraphStore(backend="neo4j", uri="bolt://localhost:7687", user="neo4j", password="password")
analytics = GraphAnalytics(store)

# Centrality
centrality  = analytics.degree_centrality(node_label="Person", relationship_type="KNOWS")
betweenness = analytics.betweenness_centrality(node_label="Person")

# Community detection
communities = analytics.detect_communities(
    node_label="Person",
    relationship_type="KNOWS",
    algorithm="louvain",
)
print(f"Detected {len(communities)} communities")

# Shortest path
path = analytics.shortest_path("alice", "charlie", relationship_type="KNOWS")
print(f"Hops: {len(path) - 1}, Path: {' → '.join(path)}")

# All paths up to max_hops
all_paths = analytics.all_paths("alice", "charlie", max_hops=4)
```

| Method | Description |
| ------ | ----------- |
| `degree_centrality(node_label, relationship_type)` | Degree-based node importance |
| `betweenness_centrality(node_label)` | Bridge-based importance |
| `pagerank(node_label, relationship_type, damping)` | PageRank scores |
| `detect_communities(node_label, relationship_type, algorithm)` | Louvain / Label Propagation |
| `shortest_path(source, target, relationship_type)` | Minimum-hop path |
| `all_paths(source, target, max_hops)` | All paths up to max depth |

## Schema Management

```python
# Index for fast label lookups
store.create_index(label="Person", property="name")

# Inspect current schema
schema = store.get_schema()
print(schema["labels"])
print(schema["indexes"])
print(schema["constraints"])
```

## Tips and Common Pitfalls

<Tip>
  **Use `NetworkX` for development, Neo4j or FalkorDB for production.** `backend="networkx"` requires zero setup and runs in memory — ideal for local development and CI tests. Switch to a persistent backend before deploying — no code changes needed, just the backend parameter.
</Tip>

<Warning>
  **Create indexes before bulk loading.** `store.create_index(label="Person", property="name")` makes `MATCH` queries on `name` orders of magnitude faster. Without indexes, every query does a full scan. Create indexes first, then load data.
</Warning>

<Tip>
  **Use `create_nodes()` and `add_edges()` for loading multiple nodes and edges.** Individual `add_node()` calls issue one network round-trip each. Loading in bulk is significantly faster for initial graph population.
</Tip>

<Warning>
  **Use parameterized queries, never string interpolation.** `store.query("WHERE n.name = $name", parameters={"name": user_input})` prevents Cypher injection attacks. Never use `f"WHERE n.name = '{user_input}'"`.
</Warning>

<Tip>
  **Enable `QueryEngine` caching for read-heavy workloads.** `QueryEngine(store, cache_ttl=300)` avoids repeated round-trips for identical queries within the cache window — useful for analytics dashboards that refresh frequently with the same aggregation queries.
</Tip>

<Warning>
  **Apache AGE requires the PostgreSQL extension installed.** `backend="apache_age"` calls the AGE extension functions. If AGE is not installed in your PostgreSQL instance, you'll get a `ProgrammingError`. See the [Apache AGE Guide](../graph_stores/apache_age) for setup instructions.
</Warning>

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
