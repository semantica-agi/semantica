---
title: "Visualization Module"
description: "Interactive and static knowledge graph, ontology, embedding, and temporal visualization."
icon: "chart-bar"
---

`semantica.visualization` renders knowledge graphs, ontologies, embedding spaces, and temporal data as interactive HTML or static images — without launching the full Explorer server.

## What You Get

- **`GraphVisualizer`** — interactive HTML (PyVis) and static image (Matplotlib) graph rendering
- **`OntologyVisualizer`** — class hierarchy and property relationship visualization
- **`EmbeddingVisualizer`** — UMAP, t-SNE, and PCA dimensionality reduction plots
- **`TemporalVisualizer`** — timeline views and animated graph evolution
- **`DistanceVisualizer`** — ego-mode neighborhood views and distance matrix heatmaps (v0.5.0)

## GraphVisualizer

```python
from semantica.visualization import GraphVisualizer

viz = GraphVisualizer()

# Interactive HTML — opens in browser, supports hover and click
viz.visualize(graph, output="graph.html")

# Static image — for reports and export
viz.visualize(graph, output="graph.png", backend="matplotlib")

# Display inline (Jupyter or default browser)
viz.show(graph)
```

### Layout and Styling Options

```python
viz.visualize(
    graph,
    output="graph.html",
    layout="force_directed",   # "force_directed" | "hierarchical" | "circular" | "spring"
    node_color_by="type",      # color nodes by entity type attribute
    edge_label="relation",     # show edge relationship labels
    max_nodes=500              # limit rendering for large graphs
)
```

### Layout Options

| Layout | Description | Best For |
| ------ | ----------- | -------- |
| `force_directed` | Physics simulation — clusters emerge naturally | General graphs |
| `hierarchical` | Top-down tree layout | Taxonomies, org charts |
| `circular` | Nodes on a circle, edges as chords | Small dense graphs |
| `spring` | Spring-force layout (Fruchterman-Reingold) | Medium graphs |

## OntologyVisualizer

Visualize class hierarchies and property relationships:

```python
from semantica.visualization import OntologyVisualizer

viz = OntologyVisualizer()

# Full ontology graph
viz.visualize(ontology, output="ontology.html")

# Class hierarchy only
viz.visualize_hierarchy(ontology, output="hierarchy.html")
```

## EmbeddingVisualizer

Project high-dimensional embeddings into 2D for cluster analysis:

```python
from semantica.visualization import EmbeddingVisualizer

viz = EmbeddingVisualizer()

viz.visualize(
    embeddings=embeddings,
    labels=labels,
    output="embeddings.html",
    method="umap"       # "umap" | "tsne" | "pca"
)
```

| Method | Speed | Preserves | Best For |
| ------ | ----- | --------- | -------- |
| `umap` | Fast | Global + local structure | Large datasets, cluster discovery |
| `tsne` | Medium | Local structure | Tight cluster separation |
| `pca` | Very fast | Variance | Quick overview, linear structure |

## TemporalVisualizer

Visualize how a knowledge graph changes over time:

```python
from semantica.visualization import TemporalVisualizer

viz = TemporalVisualizer()

# Static timeline of additions and removals
viz.visualize_timeline(temporal_kg, output="timeline.html")

# Animated evolution — one frame per time step
viz.animate(temporal_kg, output="evolution.html", fps=2)
```

## DistanceVisualizer (v0.5.0)

Semantic neighborhood and distance matrix visualization from Distance Intelligence:

```python
from semantica.visualization import DistanceVisualizer

viz = DistanceVisualizer()

# Ego-mode: neighborhood of one node colored by distance band
viz.visualize_ego(
    graph,
    center_node="Apple Inc.",
    output="ego.html",
    radius=0.5    # semantic distance radius
)

# N×N distance matrix heatmap
viz.visualize_distance_matrix(
    matrix=distance_matrix,
    labels=node_labels,
    output="distance_heatmap.html"
)
```

## Graph Explorer (Full Dashboard)

For a full browser-based UI with search, path finding, and the Ontology Hub, use `semantica.explorer`:

```python
from semantica.explorer import start_explorer

start_explorer(graph=kg, port=8080)
# Opens at http://localhost:8080
```

See the [Explorer reference](explorer) for the full feature set and REST API.

<CardGroup cols={2}>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    The graph being visualized.
  </Card>
  <Card title="Ontology" icon="sitemap" href="ontology">
    Visualize ontology class structure.
  </Card>
  <Card title="Embeddings" icon="vector-square" href="embeddings">
    Generate the embeddings visualized here.
  </Card>
  <Card title="Explorer" icon="globe" href="explorer">
    Full interactive Knowledge Explorer UI.
  </Card>
</CardGroup>
