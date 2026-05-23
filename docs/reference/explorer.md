---
title: "Explorer"
description: "Interactive FastAPI dashboard for knowledge graph exploration and the Ontology Hub."
icon: "map"
---

`semantica.explorer` is a browser-based dashboard for exploring knowledge graphs, managing ontologies, and running visual analyses — no code required after launch.

## What You Get

- **Graph Explorer** — interactive node/edge search, filtering, path highlighting, and neighborhood views
- **Ontology Hub** (v0.5.0) — browse class hierarchies, infer types, run SHACL validation, align ontologies
- **Distance Intelligence** (v0.5.0) — semantic similarity search, ego-mode neighborhood views, distance heatmaps
- **REST API** — 15+ endpoints for graph data, path finding, embeddings, and semantic search
- **CLI launcher** — `semantica-explorer` command for quick local startup

## Installation

```bash
pip install "semantica[explorer]"
```

Requires `uvicorn` and `fastapi`. Included automatically with `pip install semantica[all]`.

## Launch

<CodeGroup>

```bash CLI
# Start the explorer on a saved graph
semantica-explorer --graph my_graph.json

# Custom host and port
semantica-explorer --graph my_graph.json --host 0.0.0.0 --port 8080

# Skip auto-opening the browser
semantica-explorer --graph my_graph.json --no-browser
```

```python Python
from semantica.context import ContextGraph

graph = ContextGraph(advanced_analytics=True)
# ... build or load your graph ...
graph.save_to_file("my_graph.json")

import subprocess
subprocess.run(["semantica-explorer", "--graph", "my_graph.json", "--port", "8000"])
```

```python Module
# Run directly as a Python module
import subprocess
subprocess.run(["python", "-m", "semantica.explorer", "--graph", "my_graph.json"])
```

</CodeGroup>

## CLI Reference

| Flag | Default | Description |
| ---- | ------- | ----------- |
| `--graph`, `-g` | *(required)* | Path to a ContextGraph JSON file |
| `--port`, `-p` | `8000` | Port to bind the server |
| `--host` | `127.0.0.1` | Host to bind the server |
| `--no-browser` | `false` | Skip auto-opening the browser |

## Features

### Graph Explorer

Core dashboard for navigating knowledge graphs:

- **Indexed search** — find any node by label or type; 0.004ms on 118k-node graphs (v0.5.0)
- **Bidirectional path finding** — trace paths between any two nodes
- **Neighbor expansion** — click any node to expand its connections
- **Filter by entity type** — focus on Person, Organization, Event, or any custom type
- **Edge label display** — relationship types shown on all edges
- **Graph declutter** — workspace layout controls for dense graphs

### Ontology Hub (v0.5.0)

Full ontology lifecycle management in the browser:

- **Visual ontology editor** — drag-and-drop class and property authoring
- **SHACL Studio** — create, validate, and test SHACL shapes with live feedback
- **Alignment authoring** — author ontology alignments across schemas
- **Health dashboard** — graph quality metrics, validation status, coverage reports
- **Version control** — snapshot, diff, and restore ontology versions

### Distance Intelligence (v0.5.0)

Semantic neighborhood analysis centered on any node:

- **N×N distance matrices** — pairwise semantic distances across a set of nodes
- **Ego-mode visualization** — focus on a single node's semantic neighborhood
- **Distance band classification** — nodes grouped as `near` / `mid` / `far`
- **Embedding cache** — optimized embedding reuse for large graphs

### Knowledge Explorer API

Full FastAPI backend accessible at `http://localhost:8000/docs`:

- 12+ export formats (RDF, Parquet, AQL, JSON-LD, and more)
- WebSocket progress streaming for long operations
- Thread-safe sessions with rollback protection
- Audit trail for all operations

## API Endpoints

The FastAPI server exposes a REST API alongside the browser dashboard:

| Endpoint | Method | Description |
| -------- | ------ | ----------- |
| `/api/graph/summary` | `GET` | Node count, edge count, entity types |
| `/api/graph/search` | `GET` | Full-text and type-filtered node search |
| `/api/graph/path` | `GET` | Bidirectional path between two nodes |
| `/api/graph/neighbors` | `GET` | Neighbors of a node with optional depth |
| `/api/ontology/validate` | `POST` | Run SHACL validation on the graph |
| `/api/export/{format}` | `GET` | Export graph in specified format |
| `/ws/progress` | `WS` | WebSocket stream for operation progress |

Full OpenAPI docs available at `http://localhost:8000/docs` when the server is running.

<CardGroup cols={2}>
  <Card title="Context" icon="brain" href="context">
    Build and save the ContextGraph that Explorer loads.
  </Card>
  <Card title="Ontology" icon="sitemap" href="ontology">
    Programmatic ontology management and SHACL generation.
  </Card>
  <Card title="Visualization" icon="chart-network" href="visualization">
    Programmatic graph rendering without the Explorer server.
  </Card>
  <Card title="Export" icon="file-export" href="export">
    Export to RDF, Parquet, AQL without launching a server.
  </Card>
</CardGroup>
