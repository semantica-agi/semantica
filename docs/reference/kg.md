---
title: "Knowledge Graph Module"
description: "Graph construction, temporal models, analytics, and distance intelligence."
icon: "diagram-project"
---

`semantica.kg` transforms extracted entities and relationships into structured, queryable knowledge graphs. It includes temporal support, a full suite of graph analytics algorithms, node embeddings, and Distance Intelligence (v0.5.0).

## What You Get

<CardGroup cols={2}>
  <Card title="GraphBuilder" icon="hammer">
    Construct graphs from entities and relationships with automatic entity merging.
  </Card>
  <Card title="TemporalGraphQuery" icon="clock">
    Time-aware queries — filter by `valid_from`/`valid_until`, range queries, and evolution analysis.
  </Card>
  <Card title="ConnectivityAnalyzer" icon="circle-nodes">
    Connected components, bridge detection, and edge density analysis.
  </Card>
  <Card title="CentralityCalculator" icon="star">
    PageRank, degree, betweenness, closeness, and eigenvector centrality.
  </Card>
  <Card title="CommunityDetector" icon="users">
    Louvain, Leiden, Label Propagation, and K-Clique community detection.
  </Card>
  <Card title="PathFinder" icon="route">
    Dijkstra, A\*, BFS, and K-Shortest path algorithms.
  </Card>
</CardGroup>

<Tip>
  For conflict detection and advanced entity resolution, use `semantica.conflicts` and `semantica.deduplication` alongside this module.
</Tip>

<img src="/assets/img/diagrams/kg-structure.svg" alt="Knowledge graph entity and relation structure: Person, Organization, Location, Date nodes with typed labeled edges" style={{ width: '100%', borderRadius: '12px', margin: '0 0 24px' }} />

## Quick Start

<Steps>
  <Step title="Build the graph from extracted entities and relationships">
    ```python
    from semantica.kg import GraphBuilder

    builder = GraphBuilder(merge_entities=True)
    kg      = builder.build(entities=entities, relationships=relationships)

    print(f"Nodes: {kg.node_count}, Edges: {kg.edge_count}")
    ```
  </Step>
  <Step title="Run centrality analysis to find key nodes">
    ```python
    from semantica.kg import CentralityCalculator

    calc     = CentralityCalculator()
    pagerank = calc.calculate_pagerank(kg, damping_factor=0.85)
    top_10   = calc.get_top_nodes(pagerank, top_k=10)

    for node_id, score in top_10:
        print(f"  {node_id}: {score:.4f}")
    ```
  </Step>
  <Step title="Detect thematic communities">
    ```python
    from semantica.kg import CommunityDetector

    detector    = CommunityDetector()
    communities = detector.detect_communities(kg, algorithm="louvain")
    metrics     = detector.calculate_community_metrics(kg, communities)

    print(f"Communities: {len(communities)}")
    ```
  </Step>
  <Step title="Persist to a graph database">
    ```python
    from semantica.graph_store import GraphStore

    store = GraphStore(backend="neo4j", uri="bolt://localhost:7687",
                       user="neo4j", password="password")
    store.add_nodes_bulk(kg.entities,      batch_size=1000)
    store.add_edges_bulk(kg.relationships, batch_size=1000)
    ```
  </Step>
</Steps>

## GraphBuilder

Constructs knowledge graphs from extracted entities and relationships:

```python
from semantica.kg import GraphBuilder

builder = GraphBuilder(merge_entities=True)
kg      = builder.build(entities=entities, relationships=relationships)
```

| Method | Description |
| ------ | ----------- |
| `build(sources)` | Build graph from multiple data sources |
| `build_single_source(data)` | Build graph from a single data source |
| `merge_entities()` | Deduplicate and merge entities during construction |

<Warning>
  Always use `merge_entities=True` in production. Without it, "Steve Jobs" extracted from five different documents creates five separate person nodes. `GraphBuilder(merge_entities=True)` uses edit distance matching to consolidate them at build time.
</Warning>

## Temporal Queries

Use `TemporalGraphQuery` to run time-aware queries against a knowledge graph whose relationships carry `valid_from` / `valid_until` fields:

```python
from semantica.kg import TemporalGraphQuery
from datetime import datetime

query_engine = TemporalGraphQuery(
    enable_temporal_reasoning=True,
    temporal_granularity="day",
)

# Point-in-time query — returns only edges valid at the given time
result_2021 = query_engine.query_at_time(kg, query="", at_time=datetime(2021, 6, 15))
result_2023 = query_engine.query_at_time(kg, query="", at_time=datetime(2023, 1, 1))

# Compare what changed between two snapshots
added = [
    r for r in result_2023["relationships"]
    if r not in result_2021["relationships"]
]
print(f"New edges since 2021: {len(added)}")

# Range query — edges valid within a time window
range_result = query_engine.query_time_range(kg, query="", start_time=datetime(2020, 1, 1), end_time=datetime(2023, 1, 1))

# Evolution analysis
evolution = query_engine.analyze_evolution(kg)
```

<Note>
  Relationships added without `valid_from`/`valid_until` are treated as **always-valid**. For historical data, always attach timestamps — otherwise point-in-time queries return misleading results.
</Note>

## Graph Analytics

<Tabs>
  <Tab title="Centrality">
    Identify the most structurally important nodes in your graph:

    ```python
    from semantica.kg import CentralityCalculator

    calc = CentralityCalculator()

    pagerank    = calc.calculate_pagerank(kg, damping_factor=0.85)
    degree      = calc.calculate_degree_centrality(kg)
    betweenness = calc.calculate_betweenness_centrality(kg)
    closeness   = calc.calculate_closeness_centrality(kg)
    eigenvector = calc.calculate_eigenvector_centrality(kg)
    all_metrics = calc.calculate_all_centrality(kg)

    top_nodes = calc.get_top_nodes(pagerank, top_k=10)
    ```

    | Measure | Best For |
    | ------- | -------- |
    | PageRank | Overall importance (link-based) |
    | Degree | Most connected nodes |
    | Betweenness | Bridge / bottleneck nodes |
    | Closeness | Fastest to reach all others |
    | Eigenvector | Connected to other important nodes |
  </Tab>
  <Tab title="Community Detection">
    Partition the graph into thematically dense clusters:

    ```python
    from semantica.kg import CommunityDetector

    detector = CommunityDetector()

    # Louvain — fast, high quality (default)
    communities = detector.detect_communities(kg, algorithm="louvain")

    # Leiden — higher quality, slower
    leiden_communities = detector.detect_communities_leiden(kg, resolution=1.2)

    metrics = detector.calculate_community_metrics(kg, communities)
    print(f"Communities: {len(communities)}")
    ```

    Algorithms available: **Louvain**, **Leiden**, **Label Propagation**, **K-Clique Communities**.

    <Tip>
      Community detection finds thematic clusters — often corresponding to real-world subject groups. Use cluster membership as context boundaries for GraphRAG retrieval.
    </Tip>
  </Tab>
  <Tab title="Path Finding">
    Find shortest and alternative paths between nodes:

    ```python
    from semantica.kg import PathFinder

    finder = PathFinder()

    path    = finder.dijkstra_shortest_path(kg, "node_a", "node_b")
    paths   = finder.all_shortest_paths(kg, "source", "target")
    k_paths = finder.find_k_shortest_paths(kg, "source", "target", k=3)
    ```

    Algorithms: **Dijkstra**, **A\***, **BFS**, **All Shortest Paths**, **K-Shortest Paths**.
  </Tab>
  <Tab title="Connectivity">
    Analyse graph structure — components, bridges, and density:

    ```python
    from semantica.kg import ConnectivityAnalyzer

    analyzer   = ConnectivityAnalyzer()
    components = analyzer.find_connected_components(kg)
    density    = analyzer.calculate_density(kg)
    bridges    = analyzer.find_bridges(kg)

    print(f"Components: {len(components)}, Largest: {len(components[0])} nodes")
    print(f"Density:    {density:.4f}")
    print(f"Bridges:    {bridges}")
    ```

    | Method | Returns | Description |
    | ------ | ------- | ----------- |
    | `find_connected_components(kg)` | `List[List[str]]` | Groups of mutually reachable nodes |
    | `calculate_density(kg)` | `float` | Edge density (actual / possible edges) |
    | `find_bridges(kg)` | `List[str]` | Nodes whose removal disconnects the graph |
  </Tab>
  <Tab title="Link Prediction">
    Predict which edges are likely missing from the graph:

    ```python
    from semantica.kg import LinkPredictor

    predictor = LinkPredictor(method="preferential_attachment")
    links     = predictor.predict_links(kg, top_k=20)
    score     = predictor.score_link(kg, "node_a", "node_b")
    ```

    Algorithms: **Preferential Attachment**, **Common Neighbors**, **Jaccard**, **Adamic-Adar**, **Resource Allocation**.
  </Tab>
  <Tab title="Node Embeddings">
    Compute structural embeddings for similarity search and downstream ML:

    ```python
    from semantica.kg import NodeEmbedder

    embedder      = NodeEmbedder(method="node2vec", embedding_dimension=128)
    embeddings    = embedder.compute_embeddings(graph_store, ["Entity"], ["RELATED_TO"])
    similar_nodes = embedder.find_similar_nodes(graph_store, "entity_123", top_k=10)
    ```

    Algorithms: **Node2Vec**, **DeepWalk**, **Word2Vec**.
  </Tab>
</Tabs>

## Algorithm Summary

| Category | Algorithms | Use Cases |
| -------- | ---------- | --------- |
| Node Embeddings | Node2Vec, DeepWalk, Word2Vec | Structural similarity, node representation |
| Path Finding | Dijkstra, A\*, BFS, K-Shortest | Route planning, network analysis |
| Link Prediction | Preferential Attachment, Jaccard, Adamic-Adar | Network completion |
| Centrality | Degree, Betweenness, Closeness, PageRank | Influence analysis |
| Community Detection | Louvain, Leiden, Label Propagation | Social clustering |
| Connectivity | Components, Bridges, Density | Network robustness |

## SeedManager

Load and inject curated seed data into a knowledge graph:

```python
from semantica.kg import SeedManager

manager    = SeedManager()
seed_data  = manager.load_seed("seeds/domain_entities.json")
normalized = manager.normalize(seed_data, source="manual_curation_v1")

builder = GraphBuilder(merge_entities=True)
kg      = builder.build(normalized + extracted_sources)
```

## MethodRegistry

Register custom KG construction methods and dispatch by name:

```python
from semantica.kg import method_registry

def my_kg_builder(entities, relationships, **kwargs):
    filtered = [e for e in entities if e["confidence"] >= 0.9]
    return {"entities": filtered, "relationships": relationships}

method_registry.register("build", "high_confidence", my_kg_builder)

from semantica.kg import build_knowledge_graph
kg = build_knowledge_graph(sources, method="high_confidence")
```

## ProvenanceTracker

Track entity and relationship lineage within a knowledge graph:

```python
from semantica.kg import ProvenanceTracker

tracker = ProvenanceTracker()

tracker.track_entity(
    entity_id="apple_inc",
    source="sec_filing_2024q1.pdf",
    source_location="page 3, paragraph 2",
    source_quote="Apple Inc. reported revenue of...",
    confidence=0.98,
)

lineage = tracker.get_lineage("apple_inc")
for entry in lineage.entries:
    print(f"  Source: {entry.source}  ({entry.timestamp})")
```

For full W3C PROV-O compliance and provenance export, see the [Provenance module](provenance).

## Configuration

```yaml
kg:
  resolution:
    threshold: 0.9
    strategy: semantic

  temporal:
    enabled: true
    default_validity: infinite
```

## Tips and Common Pitfalls

<Warning>
  **Deduplicate before `GraphBuilder`, not after.** It's far easier to merge entities before they become nodes than to update all relationship endpoints after the fact. Run `DuplicateDetector` on extracted entities before calling `builder.build()`.
</Warning>

<Tip>
  **PageRank identifies your most connected, important nodes.** If you're not sure which entities in your graph are the most structurally significant, `CentralityCalculator.calculate_pagerank()` gives you a ranked list — useful for GraphRAG context anchoring.
</Tip>

<Tip>
  **Community detection finds thematic clusters.** `CommunityDetector` with Louvain partitions your graph into clusters of densely-connected nodes — often corresponding to real-world thematic groups. Use these clusters for exploratory analysis and to scope GraphRAG retrieval.
</Tip>

<Tip>
  **`ProvenanceTracker` links entities back to their source documents.** Use it during graph construction so you can always answer "where did this fact come from?" — critical for compliance and for debugging incorrect graph data.
</Tip>

<CardGroup cols={2}>
  <Card title="Graph Store" icon="server" href="graph_store">
    Persist graphs in Neo4j, FalkorDB, or Apache AGE.
  </Card>
  <Card title="Semantic Extract" icon="magnifying-glass" href="semantic_extract">
    Source of entities and relationships fed to GraphBuilder.
  </Card>
  <Card title="Visualization" icon="chart-bar" href="visualization">
    Visualize knowledge graphs interactively.
  </Card>
  <Card title="Conflicts" icon="triangle-exclamation" href="conflicts">
    Conflict detection and resolution.
  </Card>
</CardGroup>

### Cookbooks

- [Building Knowledge Graphs](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/07_Building_Knowledge_Graphs.ipynb) — fundamentals of KG construction · Beginner
- [Your First Knowledge Graph](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/08_Your_First_Knowledge_Graph.ipynb) — entity extraction to visualization · Beginner
- [Graph Analytics](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/10_Graph_Analytics.ipynb) — centrality and community detection · Intermediate
- [Advanced Graph Analytics](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/02_Advanced_Graph_Analytics.ipynb) — PageRank, Louvain, shortest path · Advanced
- [Temporal Knowledge Graphs](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/10_Temporal_Knowledge_Graphs.ipynb) — temporal logic and graph evolution · Advanced
