---
name: visualize
description: Visualize the Semantica knowledge graph — topology, centrality, communities, paths, embeddings, decision insights, and temporal evolution. Uses GraphAnalyzer, CentralityCalculator, CommunityDetector, PathFinder, and ContextGraph analytics. Sub-commands: topology, centrality, community, path, decision-graph, insights, temporal, embedding.
---

# /semantica:visualize

Render graph visualizations as Mermaid, ASCII, or structured Markdown. Usage: `/semantica:visualize <sub-command> [args]`

`$ARGUMENTS` = sub-command + optional node label or filter.

---

## `topology [--filter <node_type>]`

Full graph structure analysis — node types, edge distribution, connectivity metrics.

```python
from semantica.kg.graph_analyzer import GraphAnalyzer
from semantica.context import ContextGraph

graph = ContextGraph(advanced_analytics=True)
analyzer = GraphAnalyzer()

# Comprehensive analysis
analysis = analyzer.analyze_graph(graph=graph.to_dict())
metrics = analyzer.compute_metrics(graph=graph)
connectivity = analyzer.analyze_connectivity(graph=graph)
```

Output:
```
Graph Topology:
  Nodes:         N (M types)
  Edges:         P
  Density:       0.23
  Avg degree:    4.7
  Connected:     YES / NO (K components)

Node type distribution:
  [Mermaid pie chart]
  | Type | Count | % | Avg Degree |

Top-10 connected nodes:
  | Node | Type | Degree | Betweenness |
```

---

## `centrality [--type degree|betweenness|closeness|eigenvector|pagerank|all] [--top N]`

Calculate and rank nodes by centrality.

```python
from semantica.kg.centrality_calculator import CentralityCalculator
from semantica.context import ContextGraph

graph = ContextGraph()
calc = CentralityCalculator()

if centrality_type == "all" or not centrality_type:
    scores = calc.calculate_all_centrality(graph=graph)
elif centrality_type == "degree":
    scores = calc.calculate_degree_centrality(graph=graph)
elif centrality_type == "betweenness":
    scores = calc.calculate_betweenness_centrality(graph=graph)
elif centrality_type == "closeness":
    scores = calc.calculate_closeness_centrality(graph=graph)
elif centrality_type == "eigenvector":
    scores = calc.calculate_eigenvector_centrality(graph=graph)
elif centrality_type == "pagerank":
    scores = calc.calculate_pagerank(
        graph=graph,
        max_iterations=20,
        damping_factor=0.85,
    )
```

Return: `| Rank | Node | Type | Degree | Betweenness | Closeness | Eigenvector | PageRank |`

For a single node, also call `ContextGraph.get_node_centrality(node_id)` and `get_node_importance(node_id)`.

---

## `community [--algorithm louvain|leiden|label-propagation|overlapping]`

Detect and visualize graph communities/clusters.

```python
from semantica.kg.community_detector import CommunityDetector
from semantica.context import ContextGraph

graph = ContextGraph()
detector = CommunityDetector()

algorithm = algo_arg or "louvain"

if algorithm == "louvain":
    result = detector.detect_communities_louvain(graph, resolution=1.0)
elif algorithm == "leiden":
    result = detector.detect_communities_leiden(graph, resolution=1.0)
elif algorithm == "label-propagation":
    result = detector.detect_communities_label_propagation(graph)
elif algorithm == "overlapping":
    result = detector.detect_overlapping_communities(graph)
else:
    result = detector.detect_communities(graph, algorithm=algorithm)

structure = detector.analyze_community_structure(graph, result)
metrics = detector.calculate_community_metrics(graph, result)
```

Output:
```
Community Detection (algorithm: louvain)
  Communities: N
  Modularity:  0.71

Community summary:
  | ID | Size | Top Node | Internal Density | Bridge Nodes |

[Mermaid graph TD — nodes colored/grouped by community ID]
```

---

## `path <n1> <n2> [--k N] [--algorithm bfs|dijkstra|astar|k-shortest]`

Find and visualize paths between two nodes.

```python
from semantica.kg.path_finder import PathFinder
from semantica.context import ContextGraph

graph = ContextGraph()
finder = PathFinder()

k = int(k_arg) if k_arg else 3

if algorithm == "bfs":
    path = finder.bfs_shortest_path(graph, source=n1, target=n2)
    paths = [path]
elif algorithm == "dijkstra":
    path = finder.dijkstra_shortest_path(graph, source=n1, target=n2)
    paths = [path]
else:  # default: k-shortest
    paths = finder.find_k_shortest_paths(graph, source=n1, target=n2, k=k)

lengths = [finder.path_length(graph, p) for p in paths]
```

Output as Mermaid `sequenceDiagram` for each path:
```
Path 1 (length: 2.3):
  n1 →[rel_type]→ Middle →[rel_type]→ n2

Path 2 (length: 3.7): ...
```

---

## `decision-graph [--category <cat>] [--depth N]`

Visualize the decision influence graph for a category or all decisions.

```python
from semantica.context import ContextGraph
from semantica.context.causal_analyzer import CausalChainAnalyzer
from semantica.context import AgentContext

ctx = AgentContext(decision_tracking=True, advanced_analytics=True)
graph = ContextGraph(advanced_analytics=True)

# Get decision insights
insights = graph.get_decision_insights()

# Build causal network
analyzer = CausalChainAnalyzer(graph_store=ctx.graph_store)
network = analyzer.analyze_causal_network()
```

Output as Mermaid `graph TD` with:
- Node size proportional to causal impact score
- Color by outcome (green=approved, red=rejected, yellow=deferred)
- Edge labels showing relationship type

---

## `insights`

Comprehensive decision analytics dashboard.

```python
from semantica.context import ContextGraph, AgentContext

ctx = AgentContext(decision_tracking=True, advanced_analytics=True, kg_algorithms=True)
graph = ContextGraph(advanced_analytics=True, centrality_analysis=True)

insights = graph.get_decision_insights()
summary = graph.get_decision_summary()
graph_summary = graph.get_graph_summary()
context_insights = ctx.get_context_insights()
```

Output a full analytics dashboard:
```
Decision Intelligence Dashboard
════════════════════════════════
Decisions:         N total (M active)
Categories:        K unique
Avg confidence:    0.87
Outcome split:     approved 55% | rejected 30% | deferred 15%
Causal chains:     P chains, longest: Q hops
Loops detected:    R circular dependencies

Graph health:
  Nodes:           N  |  Edges: M  |  Density: 0.23
  Communities:     K  |  Isolated nodes: J

[Mermaid pie — outcome distribution]
[Mermaid bar — decisions by category]
```

---

## `temporal [--node <id>] [--start <date>] [--end <date>]`

Analyze how the graph evolved over time.

```python
from semantica.kg.graph_analyzer import GraphAnalyzer
from semantica.context import ContextGraph

graph = ContextGraph()
analyzer = GraphAnalyzer()

evolution = analyzer.analyze_temporal_evolution(
    graph=graph,
    start_time=start_date or None,
    end_time=end_date or None,
    metrics=["node_count", "edge_count", "density", "communities"],
)

# For a specific node, use ContextGraph.state_at()
if node_id:
    snapshot = graph.state_at(timestamp=end_date or "now")
```

Output as Markdown timeline with metrics per interval.
