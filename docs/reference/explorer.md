---
title: "Explorer"
description: "Interactive FastAPI dashboard for knowledge graph exploration and the Ontology Hub."
icon: "map"
---

`semantica.explorer` is a browser-based dashboard for exploring knowledge graphs, managing ontologies, and running visual analyses — no code required after launch.

## What You Get

<CardGroup cols={2}>
  <Card title="Graph Explorer" icon="diagram-project">
    Interactive node/edge search, filtering, path highlighting, and neighborhood expansion. Indexed search at 0.004ms on 118k-node graphs.
  </Card>
  <Card title="Ontology Hub (v0.5.0)" icon="sitemap">
    Visual ontology editor, SHACL Studio, alignment authoring, health dashboard, and version control — all in the browser.
  </Card>
  <Card title="Distance Intelligence (v0.5.0)" icon="circle-nodes">
    Semantic similarity search, ego-mode neighborhood views, N×N distance heatmaps, and distance band classification.
  </Card>
  <Card title="REST API" icon="code">
    15+ endpoints for graph data, path finding, embeddings, semantic search, analytics, and export — fully documented at `/docs`.
  </Card>
  <Card title="WebSocket Progress" icon="bolt">
    Long-running exports and analyses stream progress events in real time — no polling required.
  </Card>
  <Card title="CLI Launcher" icon="terminal">
    `semantica-explorer --graph my_graph.json` for instant local startup without writing any Python.
  </Card>
</CardGroup>

## Installation

```bash
pip install "semantica[explorer]"
```

Requires `uvicorn` and `fastapi`. Included automatically with `pip install semantica[all]`.

## Launch

<Steps>
  <Step title="Save your graph and launch Explorer">
    ```python
    import json
    from semantica.kg import GraphBuilder

    kg = GraphBuilder().build(entities=entities, relationships=relationships)

    # Export graph to JSON file
    with open("my_graph.json", "w") as f:
        json.dump({"entities": kg.entities, "relationships": kg.relationships}, f)
    ```

    ```bash
    semantica-explorer --graph my_graph.json
    # → Serving at http://127.0.0.1:8000
    ```
  </Step>
  <Step title="Custom host and port">
    ```bash
    semantica-explorer --graph my_graph.json --host 0.0.0.0 --port 8080

    # Skip auto-opening the browser
    semantica-explorer --graph my_graph.json --no-browser
    ```
  </Step>
  <Step title="Switch graphs without restarting">
    ```bash
    curl -X POST http://localhost:8000/api/import \
      -H "Content-Type: multipart/form-data" \
      -F "file=@updated_graph.json"
    # Browser dashboard reloads automatically
    ```
  </Step>
</Steps>

## CLI Reference

| Flag | Default | Description |
| ---- | ------- | ----------- |
| `--graph`, `-g` | *(required)* | Path to a saved graph JSON file |
| `--port`, `-p` | `8000` | Port to bind the server |
| `--host` | `127.0.0.1` | Host to bind the server |
| `--no-browser` | `false` | Skip auto-opening the browser |
| `--enable-auth` | `false` | Require `X-API-Key` header on all requests |
| `--api-key` | `None` | API key value when `--enable-auth` is set |
| `--cors-origins` | `"*"` | Comma-separated list of allowed CORS origins |
| `--log-level` | `"info"` | Uvicorn log level |

## Features

<Tabs>
  <Tab title="Graph Explorer">
    Core dashboard for navigating knowledge graphs:

    - **Indexed search** — find any node by label or type; 0.004ms on 118k-node graphs (v0.5.0)
    - **Bidirectional path finding** — trace paths between any two nodes
    - **Neighbor expansion** — click any node to expand its connections
    - **Filter by entity type** — focus on Person, Organization, Event, or any custom type
    - **Edge label display** — relationship types shown on all edges
    - **Graph declutter** — workspace layout controls for dense graphs
  </Tab>
  <Tab title="Ontology Hub (v0.5.0)">
    Full ontology lifecycle management in the browser:

    - **Visual ontology editor** — drag-and-drop class and property authoring
    - **SHACL Studio** — create, validate, and test SHACL shapes with live feedback
    - **Alignment authoring** — author ontology alignments across schemas
    - **Health dashboard** — graph quality metrics, validation status, coverage reports
    - **Version control** — snapshot, diff, and restore ontology versions
  </Tab>
  <Tab title="Distance Intelligence (v0.5.0)">
    Semantic neighborhood analysis centered on any node:

    - **N×N distance matrices** — pairwise semantic distances across a set of nodes
    - **Ego-mode visualization** — focus on a single node's semantic neighborhood
    - **Distance band classification** — nodes grouped as `near` / `mid` / `far`
    - **Embedding cache** — optimized embedding reuse for large graphs
  </Tab>
  <Tab title="Session Management">
    Thread-safe sessions with rollback protection:

    - Sessions are per connected browser tab
    - Write operations (annotate, import) roll back automatically on failure
    - All writes appended to audit trail at `/api/provenance/audit`
    - Session state held in memory — use `/api/export/json` to persist between restarts
  </Tab>
</Tabs>

## API Endpoints

Full interactive docs at `http://localhost:8000/docs`. All endpoints available via REST.

<AccordionGroup>
  <Accordion title="Graph endpoints">

    | Endpoint | Method | Description |
    | -------- | ------ | ----------- |
    | `/api/graph/summary` | `GET` | Node count, edge count, entity type distribution |
    | `/api/graph/search` | `GET` | Indexed full-text and type-filtered node search |
    | `/api/graph/node/{id}` | `GET` | Fetch a single node with all properties |
    | `/api/graph/neighbors` | `GET` | Neighbors of a node — `?node_id=&depth=2` |
    | `/api/graph/path` | `GET` | Bidirectional shortest path — `?source=&target=` |
    | `/api/graph/subgraph` | `POST` | Extract a subgraph by node IDs or type filter |
    | `/api/graph/annotate` | `POST` | Add a user annotation to a node or edge |
    | `/api/graph/annotations` | `GET` | List all annotations on the graph |

  </Accordion>
  <Accordion title="Ontology endpoints">

    | Endpoint | Method | Description |
    | -------- | ------ | ----------- |
    | `/api/ontology/classes` | `GET` | List all ontology classes and properties |
    | `/api/ontology/validate` | `POST` | Run SHACL validation; returns violations |
    | `/api/ontology/hierarchy` | `GET` | Class hierarchy as a tree structure |
    | `/api/ontology/vocabulary` | `GET` | SKOS vocabulary terms and alt labels |
    | `/api/ontology/align` | `POST` | Submit two ontologies for alignment |
    | `/api/ontology/diff` | `POST` | Diff two ontology versions |

  </Accordion>
  <Accordion title="Provenance, Decisions & Analytics">

    **Provenance:**

    | Endpoint | Method | Description |
    | -------- | ------ | ----------- |
    | `/api/provenance/entity/{id}` | `GET` | Full provenance lineage for an entity |
    | `/api/provenance/source/{id}` | `GET` | All entities sourced from a document |
    | `/api/provenance/audit` | `GET` | Full audit trail of Explorer operations |

    **Decisions:**

    | Endpoint | Method | Description |
    | -------- | ------ | ----------- |
    | `/api/decisions/list` | `GET` | Paginated list of recorded decisions |
    | `/api/decisions/{id}` | `GET` | Single decision with causal chain |
    | `/api/decisions/search` | `GET` | Precedent search — `?query=&limit=5` |
    | `/api/decisions/influence/{id}` | `GET` | Downstream influence of a decision |

    **Analytics:**

    | Endpoint | Method | Description |
    | -------- | ------ | ----------- |
    | `/api/analytics/centrality` | `GET` | Degree, betweenness, PageRank scores |
    | `/api/analytics/communities` | `GET` | Community detection result |
    | `/api/analytics/distance` | `POST` | N×N distance matrix for a node list |
    | `/api/analytics/neighborhood` | `GET` | Semantic neighborhood — `?node=&radius=0.4` |

  </Accordion>
  <Accordion title="SPARQL, Temporal & Export">

    **SPARQL & Temporal:**

    | Endpoint | Method | Description |
    | -------- | ------ | ----------- |
    | `/api/sparql` | `POST` | Execute a SPARQL SELECT query |
    | `/api/temporal/snapshot` | `GET` | Graph snapshot at a point in time — `?at=ISO8601` |
    | `/api/temporal/range` | `GET` | Nodes/edges active in a time range |
    | `/api/temporal/diff` | `POST` | Diff two temporal snapshots |

    **Export & Import:**

    | Endpoint | Method | Description |
    | -------- | ------ | ----------- |
    | `/api/export/{format}` | `GET` | Export in: `turtle`, `json-ld`, `ntriples`, `rdf-xml`, `parquet`, `aql`, `csv`, `owl`, `arrow`, `lpg`, `yaml`, `distance-matrix` |
    | `/api/import` | `POST` | Import a graph from file (replaces current graph in session) |

  </Accordion>
</AccordionGroup>

## WebSocket Progress

Long-running operations stream progress events over WebSocket at `ws://localhost:8000/ws/progress`:

```python
import asyncio, websockets, json

async def watch_progress():
    async with websockets.connect("ws://localhost:8000/ws/progress") as ws:
        async for message in ws:
            event = json.loads(message)
            print(f"[{event['operation']}] {event['step']} — {event['progress_pct']:.0f}%")
            if event["status"] in ("completed", "failed"):
                break

asyncio.run(watch_progress())
```

WebSocket event schema:

```json
{
  "operation":    "export",
  "step":         "serializing nodes",
  "current":      3500,
  "total":        10000,
  "progress_pct": 35.0,
  "status":       "running",
  "message":      "Serializing 10000 nodes to Turtle...",
  "error":        null
}
```

`status` values: `"running"` | `"completed"` | `"failed"` | `"cancelled"`

## Performance

| Scenario | Latency |
| -------- | ------- |
| Node search (118k nodes, indexed) | 0.004ms |
| Neighbor expansion (depth 2) | < 5ms |
| Bidirectional path (118k nodes) | < 50ms |
| SPARQL SELECT (simple pattern) | < 20ms |
| N×N distance matrix (100 nodes) | ~2s (with embedding cache) |

The node search index is built on startup. For graphs > 500k nodes, allow extra startup time before connecting.

## Tips and Common Pitfalls

<Warning>
  **Filter large graphs before saving to JSON.** The CLI loads the entire JSON file into memory. For graphs > 10k nodes, filter to the relevant subgraph (e.g., by entity type) before exporting to JSON — Explorer's force-directed layout becomes unusable on very large graphs.
</Warning>

<Warning>
  **Use authentication in shared environments.** Pass `enable_auth=True, api_key="..."` whenever Explorer is accessible to more than one person. Without auth, anyone who can reach the port can write to the graph via the annotate and import endpoints.
</Warning>

<Warning>
  **Export before the session ends.** Session state lives in memory and is lost on server restart. Call `/api/export/json` or `/api/export/turtle` to persist the current state before shutting down. Explorer does not auto-save.
</Warning>

<Tip>
  **Use WebSocket progress for long operations.** Export, analysis, and large SPARQL queries stream progress to `ws://localhost:8000/ws/progress`. Polling the REST endpoints instead gives no progress signal — use the WebSocket client so users see incremental updates.
</Tip>

<Tip>
  **Pass `session_timeout` for demos and shared notebooks.** The default session never expires. In Jupyter or shared environments, set `session_timeout=1800` (30 minutes) so stale sessions don't hold large graphs in memory.
</Tip>

<Tip>
  **Use the REST API for automation, Explorer UI for exploration.** Explorer's REST endpoints are a stable programmatic API — pipe them into scripts to automate batch annotation, SPARQL querying, or exports. The browser UI is for interactive exploration and sharing; they use the same server.
</Tip>

<CardGroup cols={2}>
  <Card title="Context" icon="brain" href="context">
    Build and save the ContextGraph that Explorer loads.
  </Card>
  <Card title="Ontology" icon="sitemap" href="ontology">
    Programmatic ontology management and SHACL generation.
  </Card>
  <Card title="Visualization" icon="chart-bar" href="visualization">
    Programmatic graph rendering without the Explorer server.
  </Card>
  <Card title="Export" icon="file-export" href="export">
    Export to RDF, Parquet, AQL without launching a server.
  </Card>
</CardGroup>
